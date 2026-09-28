"""Plan against execution: for each turn-start memo, the cards its THIS TURN plan asks us to play, and what we
actually played that turn.

    python3 research/plan_adherence.py <sim-out> --deck deck.txt [--show N]

A card counts as planned when THIS TURN names it (full name or an unambiguous nickname, as the executor's tags
match it) as the object of a play verb ("Cast Vivi", "Play Island", "Bolt Braids"), outside a conditional or
holding clause: "If the cost shows 5, cast Guttersnipe instead" is a fallback, "Keep Bolt up" and "Do not cast
Ponder" are holds, and "with Island, Mountain and Island" is mana, not a play. It is a heuristic reading of
prose; spot-check with --show. For each planned card not played, it reports
whether it was ever on offer that turn and, if so, what Jev chose instead. That is the difference between a
plan the game didn't allow and a plan the executor didn't follow.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import pilot as P  # noqa: E402
from edhkit.deck import Deck  # noqa: E402
from edhkit.scorecard import _log, _open, pod_games  # noqa: E402

_HOLDING = re.compile(r"\b(do not|don't|not|never|no|avoid|hold|keep|save|leave|without|if|unless|when|once|after)\b",
                      re.I)
_PLAY_VERB = re.compile(r"\b(cast|play|activate|equip|flash|crack|sacrifice|fire|recast|tutor|search)\w*\b", re.I)
_PAYING = re.compile(r"\b(with|using|tapping|off|from|for|plus|and)\s+([\w,'{}+-]+\s+){0,4}$", re.I)


def planned_cards(memo: str, names: list[str]) -> dict[str, str]:
    """card -> 'plan' | 'fallback' | 'hold', from the memo's THIS TURN line."""
    plan = P.memo_sections(memo).get("THIS TURN", "")
    out = {}
    for name in names:
        kinds = set()
        for at in P._card_matches(plan, name):
            num, text, fallback = P._step_around(plan, at)
            start = max(plan.rfind(". ", 0, at), plan.rfind("\n", 0, at), plan.rfind(";", 0, at),
                        plan.rfind(":", 0, at)) + 1
            prefix = plan[start:at]
            if fallback:
                kinds.add("fallback")
            elif _HOLDING.search(prefix):
                kinds.add("hold")
            elif re.fullmatch(r"\s*(\d+[.)])?\s*", prefix):  # the card as the clause's verb: "Bolt Braids"
                kinds.add("plan")
            elif _PLAY_VERB.search(prefix) and not _PAYING.search(prefix):
                kinds.add("plan")
            else:
                kinds.add("mention")  # a mana source, a condition, commentary
        if kinds:
            out[name] = next(k for k in ("plan", "fallback", "hold", "mention") if k in kinds)
    return out


def played_by_turn(sim: Path) -> dict[tuple[str, int], list[str]]:
    """(game key, turn) -> our casts, activations and land plays that turn."""
    out = defaultdict(list)
    for pod, g, us, body in pod_games(sim):
        key, turn = f"{pod}-g{g}", None
        for line in body.splitlines():
            m = re.match(r"^Turn: Turn (\d+) \(", line)
            if m:
                turn = int(m.group(1))
                continue
            m = (re.match(rf"^Add To Stack: Ai\(\d+\)-{us} (?:cast|activated) (.+?)(?: targeting .*)?$", line)
                 or re.match(rf"^Land: Ai\(\d+\)-{us} played (.+?) \(\d+\)", line))
            if m and turn is not None:
                out[(key, turn)].append(m.group(1).strip())
    return out


def _is(card: str, played: str) -> bool:
    return played == card or played.split(" // ")[0] == card.split(" // ")[0]


def analyse(sim: Path, deck: Path) -> list[dict]:
    names = Deck.load(deck).names()
    P.set_deck_names(names)
    played = played_by_turn(sim)
    offers = defaultdict(list)  # (game, turn) -> action decisions
    memos = []
    for line in _open(_log(sim)):
        d = json.loads(line)
        if d.get("type") == "memo" and str(d.get("reason", "")).startswith("start of our turn"):
            memos.append(d)
        elif d.get("type") == "decision" and d.get("kind") == "action" and d.get("questions"):
            offers[(d["game"], d["turn"])].append(d)
    rows = []
    for m in memos:
        key = (m["game"], m["turn"])
        wanted = planned_cards(m["memo"], names)
        did = played.get(key, [])
        row = {"game": m["game"], "turn": m["turn"], "planned": [c for c, k in wanted.items() if k == "plan"],
               "held": [c for c, k in wanted.items() if k == "hold"],
               "fallback": [c for c, k in wanted.items() if k == "fallback"], "played": did, "missed": []}
        for card in row["planned"]:
            if any(_is(card, p) for p in did):
                continue
            offered, instead = False, []
            for d in offers.get(key, []):
                q = d["questions"][0]
                opts = {o["id"]: o["text"] for o in q["options"]}
                if any((mm := P._OPTION_CARD.match(t)) and _is(card, mm.group(1)) for t in opts.values()):
                    offered = True
                    a = next((a for a in d["answers"] if a["q"] == "action"), None)
                    if a:
                        instead.append(opts.get(a["choice"], a["choice"])[:60])
            row["missed"].append({"card": card, "offered": offered, "instead": instead[:3]})
        rows.append(row)
    return rows


def report(rows: list[dict], show: int = 0) -> str:
    planned = sum(len(r["planned"]) for r in rows)
    done = sum(len(r["planned"]) - len(r["missed"]) for r in rows)
    missed = [x for r in rows for x in r["missed"]]
    offered = sum(1 for x in missed if x["offered"])
    unplanned = Counter(p for r in rows for p in r["played"] if not any(_is(c, p) for c in r["planned"] + r["fallback"]))
    lines = [f"{len(rows)} turn-start memos; {planned} planned plays, {done} made that turn ({done / max(planned, 1):.0%})",
             f"  not made: {len(missed)}, of which {offered} were on offer (the executor chose otherwise) and "
             f"{len(missed) - offered} never were (no mana, countered, removed, not drawn...)",
             f"  plays the plan didn't name: {sum(unplanned.values())} (most common: "
             + ", ".join(f"{k} {v}" for k, v in unplanned.most_common(6)) + ")"]
    for r in rows[:show]:
        lines.append(f"- {r['game']} t{r['turn']}: planned {r['planned']} | played {r['played']}"
                     + "".join(f"\n    missed {x['card']}: {'on offer; chose ' + ' / '.join(x['instead']) if x['offered'] else 'never on offer'}"
                               for x in r["missed"]))
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sim")
    ap.add_argument("--deck", required=True)
    ap.add_argument("--show", type=int, default=0)
    a = ap.parse_args()
    print(report(analyse(Path(a.sim), Path(a.deck)), a.show))
