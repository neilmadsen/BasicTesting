"""What Obeka's extra upkeeps actually produced, by source, from Forge pod logs.

    python3 research/upkeep_ledger.py <sim-out> [<sim-out> ...]

After each resolved Obeka trigger ("you get that many additional upkeep steps"), every trigger our seat puts on
the stack before the next turn begins is credited to the extra upkeeps, by source card. Casts of a card we
already cast earlier that turn are counted as same-turn recasts (rebound, copies). Also: Obeka's connections
per game and the extra upkeeps they granted. Main-phase-2 triggers can leak into the window; they're rare.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

OBEKA = re.compile(r"^Damage: Obeka, Splitter of Seconds \(\d+\) deals (\d+) combat damage to Ai")
TRIG = re.compile(r"^Add To Stack: Ai\(\d+\)-(P\d+) triggered (.+?)(?: targeting.*)?$")
CAST = re.compile(r"^Add To Stack: Ai\(\d+\)-(P\d+) cast (.+?)(?: \(\d+\))?(?: targeting.*)?$")
OBEKA_CAST = re.compile(r"^Add To Stack: Ai\(\d+\)-(P\d+) cast Obeka, Splitter of Seconds")
for sim in sys.argv[1:]:
    games = conn = extra = 0
    by_source, recasts = Counter(), Counter()
    per_game_extra = []
    for log in sorted(Path(sim).glob("pod*.log")):
        for g in log.read_text(errors="replace").split("Game Result:"):
            m = OBEKA_CAST.search(g) or re.search(r"Ai\(\d+\)-(P\d+) cast Obeka", g)
            if not m:
                continue
            me = m.group(1); games += 1; g_extra = 0
            window = False; cast_this_turn = Counter()
            for line in g.splitlines():
                if line.startswith("Turn: "):
                    window = False; cast_this_turn = Counter(); continue
                if (o := OBEKA.match(line)):
                    conn += 1; extra += int(o.group(1)); g_extra += int(o.group(1)); continue
                if "you get that many additional upkeep steps" in line and line.startswith("Resolve Stack"):
                    window = True; continue
                if (c := CAST.match(line)) and c.group(1) == me:
                    name = c.group(2).strip()
                    if cast_this_turn[name] and window:
                        recasts[name] += 1
                    cast_this_turn[name] += 1
                if window and (t := TRIG.match(line)) and t.group(1) == me:
                    src = t.group(2).strip()
                    if src not in ("The Monarch",):
                        by_source[src] += 1
            per_game_extra.append(g_extra)
    print(f"\n== {Path(sim).name}: {games} games; Obeka connected {conn} times, {extra} extra upkeeps "
          f"(per game: {per_game_extra})")
    print("   triggers in extra upkeeps by source:", ", ".join(f"{k} {v}" for k, v in by_source.most_common(14)) or "-")
    print("   same-turn recasts after Obeka (rebound/copies):", ", ".join(f"{k} {v}" for k, v in recasts.most_common()) or "-")
