"""Turn audit: a model reviews the turns that matter in a piloted run and reports what went wrong, by layer, with
evidence. It does by rote what finding bugs by hand did: read the board, the memo, every decision and its tags, and
the game log, and ask whether each thing that happened is what should have happened.

    ./edh turn-audit <sim-out> --deck deck.txt [--max 40] [--workers 4] [--out findings.json]

Turns are chosen, most important first:
- turns the bug scan flagged (edhkit/bugscan.py);
- "win now" turns that didn't win;
- the last three turns of ours in every game we lost;
- turns where a play the memo planned was on offer and not made.

Each finding names its layer (engine, harness, tagging, executor, strategist), a severity, and quoted evidence;
findings without evidence are dropped. The auditor is the same model family as the strategist, so it can share its
blind spots (the Ring's evasion read backwards): it is asked to check rules claims against the card text given.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bugscan, claude_cli
from . import pilot as P
from .scorecard import _log, _open, game_place, pod_games
from .turnview import view

LAYERS = ("engine", "harness", "tagging", "executor", "strategist")

SYSTEM = (
    "You audit one turn of a simulated four-player Commander game for bugs and mistakes. Our seat is played by a "
    "pilot: a strategist model writes a memo (THIS TURN, TARGET, WIN PATH, THREAT ORDER, HOLD, REPLAN IF) at the "
    "start of our turn; a fast executor (Jev) then answers each decision the game engine (Forge) asks, choosing "
    "between Forge's own default and other options. Each option can carry tags derived from the memo "
    "(e.g. [named in the memo's THIS TURN plan, step 2: ...]); tags are how the plan reaches the executor. Some "
    "decisions are never asked and Forge's AI makes them silently (trigger order, mana payment, some targets).\n\n"
    "Find every place where what happened differs from what should have happened, and say which layer is at "
    "fault:\n"
    "- engine: Forge applied the rules wrongly (an effect didn't do what its card text says, a trigger didn't "
    "fire, a permanent vanished, a cost was wrong).\n"
    "- harness: the pilot was never asked a decision that mattered, an option was missing or mislabelled, or an "
    "answer wasn't applied as chosen.\n"
    "- tagging: the memo's plan reached the executor wrongly: a planned play untagged, a mention tagged as a "
    "play, a hold tagged as a play, a stale step still tagged after it was done or became impossible.\n"
    "- executor: Jev chose against a clear memo instruction and its tag, or made an obviously bad tactical "
    "choice the memo didn't cover.\n"
    "- strategist: the memo itself was wrong: rules misread (check the card text you are given; mind the "
    "direction of conditions), mana or damage arithmetic wrong, a lethal line missed or a non-lethal line called "
    "lethal, a trigger or draw it didn't count, a threat misjudged.\n\n"
    "Rules: judge only from what is shown. Quote the exact log lines, option texts, memo text or card text that "
    "prove each finding. Do not report opponents' play, or luck. Do not report a choice as a mistake when it is "
    "defensible; report it only when you can say concretely what should have happened instead. If nothing is "
    "wrong, return an empty list.\n\n"
    "Severity: decisive (it likely changed who won or our place), costly (it cost real resources or tempo), "
    "minor.\n\n"
    "Reply with JSON only: {\"findings\": [{\"layer\": \"...\", \"severity\": \"decisive|costly|minor\", "
    "\"title\": \"a short name for the defect, generic enough to match the same defect in another game\", "
    "\"what_happened\": \"...\", \"should_have\": \"...\", \"evidence\": [\"quoted lines\"], "
    "\"fix\": \"what change to the engine, harness, tags, executor rules or strategist prompt would prevent it\"}]}"
)

_TURN = re.compile(r"^Turn: Turn (\d+) \(Ai\(\d+\)-(P\d+)\)")
_NOISE = ("Phase:", "Mana:", "Player Control:")
_WIN_WORDS = re.compile(r"\b(win (?:now|this turn)|lethal|kill (?:both|all|P\d)|both opponents dead|"
                        r"dies? this turn|finish(?:es)? (?:P\d|them))\b", re.I)


def _turn_lines(body: str) -> dict[int, list[str]]:
    out, turn = defaultdict(list), None
    for line in body.splitlines():
        m = _TURN.match(line)
        if m:
            turn = int(m.group(1))
        if turn is not None and not line.startswith(_NOISE):
            out[turn].append(line)
    return out


def _our_turns(body: str, us: str) -> list[int]:
    return [int(m.group(1)) for line in body.splitlines() if (m := _TURN.match(line)) and m.group(2) == us]


def select(sim: Path, deck: Path, max_turns: int = 40, per_game: int = 6) -> list[dict]:
    """[{game, turn, reasons}] most important first."""
    recs = [json.loads(line) for line in _open(_log(sim))]
    memos = {(r["game"], r["turn"]): r["memo"] for r in recs if r.get("type") == "memo"}
    games = {f"{pod}-g{g}": (us, body) for pod, g, us, body in pod_games(sim)}
    picks: dict[tuple[str, int], list[str]] = defaultdict(list)
    for f in bugscan.scan(sim):
        if f["severity"] in ("high", "medium") and f.get("turn") is not None and f["game"] in games:
            picks[(f["game"], f["turn"])].append(f"bug scan: {f['check']}: {f['what'][:120]}")
    for key, (us, body) in games.items():
        ours = _our_turns(body, us)
        place = game_place(body, us)
        for t in ours:
            memo = memos.get((key, t), "")
            plan = P.memo_sections(memo).get("THIS TURN", "") + " " + P.memo_sections(memo).get("TARGET", "")
            nxt = next((x for x in ours if x > t), None)
            if memo and _WIN_WORDS.search(plan) and not (place == 1 and nxt is None):
                picks[(key, t)].append("the memo planned to win or kill this turn")
        if place and place > 1:
            for t in ours[-3:]:
                picks[(key, t)].append(f"one of our last three turns in a game we finished {place}")
    order = sorted(picks.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    out, per = [], defaultdict(int)
    for (game, turn), reasons in order:
        if per[game] >= per_game:
            continue
        per[game] += 1
        out.append({"game": game, "turn": turn, "reasons": reasons})
        if len(out) >= max_turns:
            break
    return out


def packet(sim: Path, deck: Path, game: str, turn: int, reasons: list[str], cache: dict) -> str:
    if "games" not in cache:
        cache["games"] = {f"{pod}-g{g}": (us, body) for pod, g, us, body in pod_games(sim)}
    us, body = cache["games"][game]
    lines = _turn_lines(body)
    ours = _our_turns(body, us)
    nxt = next((x for x in ours if x > turn), None)
    after = [ln for t in sorted(lines) if turn < t < (nxt or turn + 4) for ln in lines[t]
             if ln.startswith(("Turn:", "Add To Stack", "Combat", "Damage", "Zone Change", "Game Outcome"))]
    place = game_place(body, us)
    parts = [f"GAME {game}: we are {us}; we finished {place if place else 'unknown'} of 4.",
             "WHY THIS TURN WAS PICKED: " + "; ".join(reasons), "",
             view(sim, game, turn, deck), "",
             f"--- the game log for turn {turn} (our turn)", *lines.get(turn, [])[:260], "",
             "--- what happened until our next turn (casts, combat, damage, zone changes)", *after[:120]]
    return "\n".join(parts)


def _parse(text: str) -> list[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for f in data.get("findings", []):
        if f.get("layer") in LAYERS and f.get("evidence") and f.get("title"):
            out.append(f)
    return out


def audit(sim: Path, deck: Path, max_turns: int = 40, workers: int = 4, model: str = P.STRATEGIST_MODEL,
          effort: str = "medium") -> list[dict]:
    P.set_deck_names(__import__("edhkit.deck", fromlist=["Deck"]).Deck.load(deck).names())
    turns = select(sim, deck, max_turns)
    cache: dict = {}
    packets = [(t, packet(sim, deck, t["game"], t["turn"], t["reasons"], cache)) for t in turns]

    def one(item):
        t, text = item
        try:
            reply = claude_cli.run(SYSTEM, text, model, effort, timeout=600)
        except claude_cli.ClaudeCallFailed as e:
            return [{"game": t["game"], "turn": t["turn"], "error": str(e)}]
        return [dict(f, game=t["game"], turn=t["turn"]) for f in _parse(reply)]

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(one, packets))
    return [f for r in results for f in r]


_SEV = {"decisive": 0, "costly": 1, "minor": 2}


def report(findings: list[dict]) -> str:
    errors = [f for f in findings if "error" in f]
    real = [f for f in findings if "error" not in f]
    by_title = defaultdict(list)
    for f in real:
        by_title[(f["layer"], f["title"].strip().lower())].append(f)
    lines = [f"{len(real)} findings in {len({(f['game'], f['turn']) for f in real})} turns"
             + (f"; {len(errors)} audit calls failed" if errors else "")]
    for layer in LAYERS:
        group = sorted(((k, v) for k, v in by_title.items() if k[0] == layer),
                       key=lambda kv: (min(_SEV.get(f["severity"], 3) for f in kv[1]), -len(kv[1])))
        if not group:
            continue
        lines.append(f"\n## {layer} ({sum(len(v) for _, v in group)})")
        for (_, title), fs in group:
            worst = min(fs, key=lambda f: _SEV.get(f["severity"], 3))
            lines.append(f"- [{worst['severity']}] {worst['title']} — {', '.join(sorted({f['game'] + ' t' + str(f['turn']) for f in fs}))}")
            lines.append(f"    {worst.get('what_happened', '')[:300]}")
            lines.append(f"    should have: {worst.get('should_have', '')[:200]}")
            lines.append(f"    fix: {worst.get('fix', '')[:200]}")
            for e in worst.get("evidence", [])[:2]:
                lines.append(f"    > {str(e)[:200]}")
    return "\n".join(lines)


def main(sim: str, deck: str, max_turns: int, workers: int, out: str | None, dry: bool = False) -> None:
    sim_p, deck_p = Path(sim), Path(deck)
    if dry:
        for t in select(sim_p, deck_p, max_turns):
            print(t["game"], t["turn"], "|", "; ".join(t["reasons"])[:160])
        return
    findings = audit(sim_p, deck_p, max_turns, workers)
    text = report(findings)
    print(text)
    dest = Path(out) if out else sim_p / "turn_audit.json"
    dest.write_text(json.dumps(findings, indent=1))
    dest.with_suffix(".md").write_text(text)
