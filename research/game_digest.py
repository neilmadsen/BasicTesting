"""Turn-by-turn digest of piloted games, for post-mortems.

    python3 research/game_digest.py <sim-out-dir> <digest-dir>

Merges Forge's game log (casts and targets, combat, damage, life, cards leaving the
battlefield) with the pilot's decision log (--log-state: memos, boards, overrules,
holds, X choices, escalations) into one readable file per game. Needs the pod logs
and pilot_decisions.jsonl of one sim run.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit.pilot import parse_entry  # noqa: E402

AI = re.compile(r"Ai\(\d+\)-(P\d+)")
ID = re.compile(r" \(\d+\)")


def _open(p: Path):
    return gzip.open(p, "rt") if p.suffix == ".gz" else p.open()


def clean(line: str, us: str) -> str:
    line = ID.sub("", AI.sub(r"\1", line))
    return line.replace(us + " ", "US ").replace(us + ".", "US.").replace(us + ",", "US,")


def board(p: dict, n: int = 14) -> str:
    items = [e for e in p.get("battlefield", []) if "[land]" not in e]
    lands = sum(parse_entry(e)["n"] for e in p.get("battlefield", []) if "[land]" in e)
    return f"{lands} lands; " + (", ".join(items[:n]) + (f", +{len(items) - n} more" if len(items) > n else "") or "no nonland permanents")


def digest_game(tag: str, lines: list[str], seats: dict, decisions: list[dict]) -> str:
    us = next(k for k, v in seats.items() if v == "US")
    opp = ", ".join(f"{k} {v.split(' // ')[0]}" for k, v in seats.items() if v != "US")
    by_turn_dec = defaultdict(list)
    for d in decisions:
        by_turn_dec[d.get("turn")].append(d)
    out = [f"# {tag}: we are {us}; opponents {opp}"]
    outcome = [clean(l, us) for l in lines if l.startswith("Game Outcome")]
    out.append("Result: " + "; ".join(o.replace("Game Outcome: ", "") for o in outcome))
    turn, active, events = 0, "", defaultdict(list)
    life = {}
    life_at = {}
    dmg_to_us = defaultdict(lambda: defaultdict(int))
    for raw in lines:
        m = re.match(r"Turn: Turn (\d+) \(Ai\(\d+\)-(P\d+)\)", raw)
        if m:
            turn, active = int(m.group(1)), m.group(2)
            events[turn].append(f"__active {active}")
            continue
        l = clean(raw, us)
        if l.startswith("Life: Life:"):
            mm = re.match(r"Life: Life: (\w+) (-?\d+) > (-?\d+)", l)
            if mm:
                life[mm.group(1)] = int(mm.group(3))
                life_at[turn] = dict(life)
            continue
        if l.startswith("Damage:"):
            mm = re.match(r"Damage: (.+?) deals (\d+) (combat |non-combat )?damage to US\.", l)
            if mm:
                dmg_to_us[turn][f"{mm.group(1)} ({(mm.group(3) or '').strip() or 'damage'})"] += int(mm.group(2))
            continue
        if l.startswith("Add To Stack:"):
            events[turn].append(l.replace("Add To Stack: ", ""))
        elif l.startswith("Combat:") and "assigned" in l:
            events[turn].append(l.replace("Combat: ", "attack: "))
        elif l.startswith("Combat:") or re.match(r"P\d+ didn't block|US didn't block", l):
            if "blocked" in l and "didn't" not in l:
                events[turn].append(l.replace("Combat: ", "block: "))
        elif l.startswith("Zone Change:") and "from Battlefield" in l and ("Graveyard" in l or "Exile" in l or "Hand" in l):
            if "Token" not in l and "Treasure" not in l and "Food" not in l and "Clue" not in l:
                events[turn].append(l.replace("Zone Change: ", "left battlefield: "))
        elif l.startswith("Game Outcome") and "lost" in l:
            events[turn].append(l)
    for t in sorted(events):
        act = next((e.split()[1] for e in events[t] if e.startswith("__active")), "?")
        lt = life_at.get(t) or {}
        head = f"\n## Turn {t} ({'OUR TURN' if act == us else act}, round {(t + 3) // 4})"
        if lt:
            head += " | life: " + ", ".join(f"{k if k != us else 'US'} {v}" for k, v in sorted(lt.items()))
        out.append(head)
        decs = by_turn_dec.get(t, [])
        memos = [d for d in decs if d["type"] == "memo"]
        first_state = next((d["state"] for d in decs if d["type"] == "decision" and "state" in d), None)
        if first_state and act == us:
            out.append(f"Our hand: {', '.join(first_state.get('my_hand', []))}")
            out.append(f"Our graveyard ({len(first_state.get('my_graveyard', []))}): {', '.join(first_state.get('my_graveyard', [])[:20])}")
            for p in first_state["players"]:
                out.append(f"Board {'US' if p['is_me'] else p['name']}: {board(p)}")
        for m in memos:
            out.append(f"MEMO ({m['reason'][:120]}):\n{m['memo'].strip()}")
        for d in decs:
            if d["type"] == "escalation":
                out.append(f"ESCALATION (p={d['p']}): {'; '.join(d['changes'])[:300]}")
            if d["type"] != "decision":
                continue
            for a in d["answers"]:
                if a.get("unused"):
                    continue
                if a["q"] == "hold" and a["choice"] != "none":
                    out.append(f"HOLD: {a['label']}")
                elif a["q"].startswith("x_"):
                    out.append(f"X: {a['label']}")
                elif a["choice"] != a["default"]:
                    out.append(f"PILOT OVERRULED FORGE ({d['kind']}, {d['phase']}): chose [{a['label']}] "
                               f"instead of Forge's [{a.get('default_label', a['default'])}]")
        for e in events[t]:
            if not e.startswith("__active"):
                out.append(f"- {e}")
        if dmg_to_us.get(t):
            out.append("Damage to US this turn: " + ", ".join(f"{k} {v}" for k, v in dmg_to_us[t].items()))
    return "\n".join(out)


def main(sim: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    dec = defaultdict(list)
    log = sim / "pilot_decisions.jsonl"
    if not log.exists():
        log = sim / "pilot_decisions.jsonl.gz"
    for line in _open(log):
        d = json.loads(line)
        dec[d.get("game")].append(d)
    for pod in sorted(list(sim.glob("pod*.log")) or list(sim.glob("pod*.log.gz"))):
        text = _open(pod).read()
        seats = json.loads(re.search(r"^# seats: (.*)$", text, re.M).group(1))
        games = re.split(r"^===== game (\d+) =====$", text, flags=re.M)
        for i in range(1, len(games), 2):
            tag = f"{pod.name.split('.')[0]}-g{games[i]}"
            body = [l.strip() for l in games[i + 1].splitlines() if l.strip()]
            (dest / f"{tag}.md").write_text(digest_game(tag, body, seats, dec.get(tag, [])))
    print(f"wrote {len(list(dest.glob('*.md')))} digests to {dest}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
