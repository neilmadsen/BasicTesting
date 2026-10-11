"""Race timelines for piloted games we lost: when did the eventual winner's board get out of hand, and what were
we holding when it did?

    python3 research/race.py <sim-out> [<sim-out> ...] [--all]

Needs a --log-state pilot log (pilot_decisions.jsonl) and the pod logs. For each lost game (--all: every game),
one row per turn: the winner's creature power on board, the biggest other board, everyone's life, the answers
in our hand (board wipes, removal, counters, bounce/fog, by Scryfall tagger role), our mana, and what we cast.
The "window" is the first turn the winner's board power reached 20 or could kill a player outright; the summary
says which answers we held in that window and whether any of them got cast in the next four turns.

Losing in a four-player game usually means someone else won, not that we were killed by the table; this asks
whether our deck had the tools to stop the leader in time (a deck question) and whether we used them (a pilot
question).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit.cards import CardDB  # noqa: E402

PT = re.compile(r" (\d+)/(\d+)")
XN = re.compile(r" x(\d+)")
RESULT = re.compile(r"Game Result: Game (\d+) ended .*?Ai\(\d+\)-(P\d+) has won")
TURN = re.compile(r"^Turn: Turn (\d+) \(Ai\(\d+\)-(P\d+)\)")
CAST = re.compile(r"^Add To Stack: Ai\(\d+\)-(P\d+) cast (.+?)(?: \(\d+\))?(?: targeting.*)?$")
ANSWER_TAGS = [("WIPE", {"board-wipe"}), ("KILL", {"creature-removal", "spot-removal", "removal"}),
               ("CTR", {"counterspell"}), ("BOUNCE", {"bounce", "fog"})]


def players(state) -> list[dict]:
    p = state.get("players")
    return ast.literal_eval(p) if isinstance(p, str) else (p or [])


def power(battlefield: list[str]) -> int:
    tot = 0
    for e in battlefield:
        if "[land]" in e:
            continue
        m = PT.search(e)
        if m:
            n = int(XN.search(e).group(1)) if XN.search(e) else 1
            tot += int(m.group(1)) * n
    return tot


def answer_class(db: CardDB, name: str, cache: dict) -> str | None:
    if name not in cache:
        try:
            tags = set(db.require(name).tags or [])
        except KeyError:
            tags = set()
        cache[name] = next((lab for lab, want in ANSWER_TAGS if tags & want), None)
    return cache[name]


def winners(sim: Path) -> dict[str, str]:
    out = {}
    for log in sorted(sim.glob("pod*.log")):
        pod = log.stem
        for m in RESULT.finditer(log.read_text(errors="replace")):
            out[f"{pod}-g{m.group(1)}"] = m.group(2)
    return out


def casts_by_turn(sim: Path) -> dict[str, dict[int, list[tuple[str, str]]]]:
    """game id -> turn -> [(player, card)] from the pod logs (games split at each 'Game Result')."""
    out: dict[str, dict[int, list]] = {}
    for log in sorted(sim.glob("pod*.log")):
        pod, g, turn = log.stem, 1, 0
        cur: dict[int, list] = defaultdict(list)
        for line in log.read_text(errors="replace").splitlines():
            if m := TURN.match(line):
                turn = int(m.group(1))
            elif m := CAST.match(line):
                cur[turn].append((m.group(1), m.group(2)))
            elif line.startswith("Game Result:"):
                out[f"{pod}-g{g}"] = cur
                g, cur, turn = g + 1, defaultdict(list), 0
    return out


def analyze(sim: Path, db: CardDB, show_all: bool = False) -> list[str]:
    win = winners(sim)
    casts = casts_by_turn(sim)
    by_game: dict[str, dict[int, dict]] = defaultdict(dict)
    me_of: dict[str, str] = {}
    for line in (sim / "pilot_decisions.jsonl").open():
        r = json.loads(line)
        if r.get("type") != "decision" or "state" not in r:
            continue
        st = r["state"]
        t = st.get("turn") or 0
        me_of[r["game"]] = st.get("me", me_of.get(r["game"]))
        by_game[r["game"]].setdefault(t, st)          # first decision we saw in each turn
    cache: dict = {}
    out = []
    for game in sorted(by_game):
        me, w = me_of.get(game), win.get(game)
        if not show_all and w == me:
            continue
        out.append(f"\n=== {sim.name} {game}: we are {me}, winner {w}{' (US)' if w == me else ''}")
        out.append(f"{'turn':>4} {'active':>6} {'winner pow':>10} {'top other':>12} {'lives':>22} {'mana':>4}  answers in hand | we cast")
        window, held_at_window, cast_after = None, [], []
        for t in sorted(by_game[game]):
            st = by_game[game][t]
            ps = {p["name"]: p for p in players(st)}
            wp = power(ps[w]["battlefield"]) if w in ps else 0
            others = sorted(((power(p["battlefield"]), n) for n, p in ps.items() if n not in (w, me)), reverse=True)
            top = f"{others[0][0]}({others[0][1]})" if others else "-"
            lives = " ".join(f"{n}:{p['life']}" for n, p in sorted(ps.items()))
            ans = []
            for c in st.get("my_hand", []):
                lab = answer_class(db, c, cache)
                if lab:
                    ans.append(f"{lab}:{c}")
            ours = [c for p, c in casts.get(game, {}).get(t, []) if p == me]
            alive = [p["life"] for n, p in ps.items() if not p.get("lost")]
            if window is None and w != me and (wp >= 20 or any(0 < l <= wp for n, l in
                                                                ((n, p["life"]) for n, p in ps.items() if n != w))):
                window, held_at_window = t, ans
            if window is not None and t <= window + 4:
                cast_after += [c for c in ours if answer_class(db, c, cache)]
            mark = " <== window" if t == window else ""
            out.append(f"{t:>4} {st.get('active', '?'):>6} {wp:>10} {top:>12} {lives:>22} {st.get('my_mana_available', 0):>4}  "
                       f"{', '.join(ans) or '-'} | {', '.join(ours) or ''}{mark}")
        if window is not None:
            out.append(f"  window at turn {window}: held {', '.join(held_at_window) or 'NO ANSWERS'}; "
                       f"answers cast in turns {window}-{window + 4}: {', '.join(cast_after) or 'none'}")
        elif w != me:
            out.append("  no window: the winner's board never reached 20 power or a lethal attack on our view")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    db = CardDB()
    for a in args:
        print("\n".join(analyze(Path(a), db, "--all" in sys.argv)))
