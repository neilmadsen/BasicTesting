"""Loss anatomy: where our seat falls behind, and how it dies, from Forge pod logs alone.

    python3 research/loss_anatomy.py <sim-out> [<sim-out> ...]

Works on Forge-only and piloted runs alike (no pilot log needed), so an arm and its Forge baseline on the
same pods can be compared. Per game it measures our development against the average opponent (land drops,
spells cast), how much of the table's aggression lands on us, and, for games we lose, what killed us.
"""
from __future__ import annotations

import gzip
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

TURN = re.compile(r"^Turn: Turn (\d+) \(Ai\(\d+\)-(P\d+)\)")
LAND = re.compile(r"^Land: Ai\(\d+\)-(P\d+) played")
CAST = re.compile(r"^Add To Stack: Ai\(\d+\)-(P\d+) cast (.+?)(?: targeting|$)")
DMG = re.compile(r"^Damage: (.+?) \((\d+)\) deals (\d+) (combat |non-combat )?damage to Ai\(\d+\)-(P\d+)")
LIFE = re.compile(r"^Life: Life: Ai\(\d+\)-(P\d+) (-?\d+) > (-?\d+)")
WON = re.compile(r"^Game Outcome: Ai\(\d+\)-(P\d+) has won")
ATTACKERS = re.compile(r"^Combat: Ai\(\d+\)-(P\d+) assigned (.+?) to attack")


def _open(p: Path):
    return gzip.open(p, "rt") if p.suffix == ".gz" else p.open()


def games(sim: Path):
    for pod in sorted(list(sim.glob("pod*.log")) + list(sim.glob("pod*.log.gz"))):
        text = _open(pod).read()
        head = re.search(r"^# seats: (.*)$", text, re.M)
        if not head:
            continue
        seats = json.loads(head.group(1))
        us = next(k for k, v in seats.items() if v == "US")
        for body in re.split(r"^===== game \d+ =====$", text, flags=re.M)[1:]:
            yield pod.name.split(".")[0], us, seats, body.splitlines()


def anatomy(sim: Path) -> dict:
    agg, per_game = defaultdict(list), []
    for pod, us, seats, lines in games(sim):
        players = list(seats)
        turn_of = defaultdict(int)          # player -> turns taken so far
        lands = defaultdict(list)           # player -> land drops by own turn number (cumulative)
        casts_by = Counter()
        early_casts = Counter()             # casts during the player's first 5 turns
        owner = {}                          # card id -> controller (first time it shows up on the stack)
        dmg_to = defaultdict(Counter)       # target -> source player -> damage
        combat_to_us = noncombat_to_us = 0
        life = {p: 40 for p in players}
        out_at, winner, active = {}, None, None
        life_loss_us_last = Counter()       # life we lost in the 8 turns before we died, by kind
        recent = []                         # (index, kind, amount, source_player) of our life losses
        for i, line in enumerate(lines):
            m = TURN.match(line)
            if m:
                active = m.group(2)
                turn_of[active] += 1
                lands[active].append(lands[active][-1] if lands[active] else 0)
                continue
            m = LAND.match(line)
            if m and lands[m.group(1)]:
                lands[m.group(1)][-1] += 1
                continue
            m = ATTACKERS.match(line)
            if m:  # combat damage is traced to its attacker's controller through the declaration
                for cid in re.findall(r"\((\d+)\)", m.group(2)):
                    owner[cid] = m.group(1)
                continue
            m = CAST.match(line)
            if m:
                casts_by[m.group(1)] += 1
                if turn_of[m.group(1)] <= 5:
                    early_casts[m.group(1)] += 1
                continue
            m = DMG.match(line)
            if m:
                _, cid, n, kind, target = m.groups()
                src = owner.get(cid, "?")
                dmg_to[target][src] += int(n)
                if target == us:
                    if kind == "combat ":
                        combat_to_us += int(n)
                    else:
                        noncombat_to_us += int(n)
                    recent.append((i, "combat" if kind == "combat " else "non-combat damage", int(n), src))
                continue
            m = LIFE.match(line)
            if m:
                p, a, b = m.group(1), int(m.group(2)), int(m.group(3))
                life[p] = b
                if b <= 0:
                    out_at.setdefault(p, i)
                if p == us and b < a:
                    # a life loss with no damage to us in the last few lines is a drain or a payment (lifelink
                    # puts the attacker's gain line between the damage line and ours)
                    if not recent or recent[-1][0] < i - 4:
                        recent.append((i, "life loss (drain, payment)", a - b, "?"))
                continue
            m = WON.match(line)
            if m:
                winner = m.group(1)
        if not winner:
            continue
        we_won = winner == us
        # our development vs the average opponent, at our 4th and 6th turns
        def at(p, k):
            return lands[p][k - 1] if len(lands[p]) >= k else None
        opps = [p for p in players if p != us]
        for k in (4, 6):
            ours = at(us, k)
            theirs = [at(p, k) for p in opps if at(p, k) is not None]
            if ours is not None and theirs:
                agg[f"land drops by own turn {k}: us minus opponents' avg"].append(ours - st.mean(theirs))
                agg[f"land drops by own turn {k}: us"].append(ours)
        agg["spells cast: us minus opponents' avg"].append(casts_by[us] - st.mean(casts_by[p] for p in opps))
        agg["spells cast in first 5 turns: us minus opponents' avg"].append(
            early_casts[us] - st.mean(early_casts[p] for p in opps))
        # aggression aimed at us: share of all damage opponents dealt to players that hit us
        to_players = sum(sum(v for s, v in dmg_to[t].items() if s != t) for t in players)
        to_us = sum(v for s, v in dmg_to[us].items() if s != us)
        if to_players:
            agg["share of damage to players that hit us (fair share ~0.33)"].append(to_us / to_players)
        agg["combat damage we took"].append(combat_to_us)
        agg["non-combat damage we took"].append(noncombat_to_us)
        if not we_won and us in out_at:
            death = out_at[us]
            window = [r for r in recent if r[0] >= death - 400]  # roughly the last round or two
            tot = sum(r[2] for r in window) or 1
            for kind in ("combat", "non-combat damage", "life loss (drain, payment)"):
                agg[f"how we died: share from {kind}"].append(sum(r[2] for r in window if r[1] == kind) / tot)
            killer = Counter()
            for r in window:
                killer[r[3]] += r[2]
            top = killer.most_common(1)[0][0] if killer else "?"
            if top != "?":
                agg["combat death: main attacker was the eventual winner"].append(1.0 if top == winner else 0.0)
        per_game.append({"pod": pod, "won": we_won})
    out = {k: round(st.mean(v), 2) for k, v in sorted(agg.items())}
    out["games"] = len(per_game)
    return out


if __name__ == "__main__":
    rows = {Path(p).name: anatomy(Path(p)) for p in sys.argv[1:]}
    keys = sorted({k for r in rows.values() for k in r})
    w = max(len(k) for k in keys)
    print("".ljust(w) + "".join(f"  {n[-14:]:>14}" for n in rows))
    for k in keys:
        print(k.ljust(w) + "".join(f"  {str(rows[n].get(k, '-')):>14}" for n in rows))
