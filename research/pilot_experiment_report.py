"""Tabulate a pilot experiment: several `edh sim` arms run on the same pods and seeds.

    python3 research/pilot_experiment_report.py <exp_dir> forge jev-opus jev

Each arm is a sim --out folder (summary.json, podNN.log, pilot_decisions.jsonl).
Prints a markdown table of outcomes, play-pattern stats and pilot stats, a
per-pod paired view, and escalation triggers. Fisher exact p-values are
two-sided against the first arm.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit.forge import parse_games, wilson  # noqa: E402


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """2x2 table [[a, b], [c, d]]: wins/losses for two arms."""
    n1, n2, k = a + b, c + d, a + c
    n = n1 + n2

    def p(x: int) -> float:
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)

    p_obs = p(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p_obs * (1 + 1e-9)))


def pod_results(arm: Path) -> list[list[str]]:
    """Per pod, per game: 'W' (we won), 'L', or 'D' (draw/timeout)."""
    out = []
    for log in sorted(arm.glob("pod*.log")) or sorted(arm.glob("pod*.log.gz")):
        text = gzip.open(log, "rt").read() if log.suffix == ".gz" else log.read_text()
        seats = json.loads(re.search(r"^# seats: (.*)$", text, re.M).group(1))
        us = next(k for k, v in seats.items() if v == "US")
        res = []
        for g, _ in parse_games(text):
            res.append("D" if g.timeout or g.winner is None else "W" if g.winner == us else "L")
        out.append(res)
    return out


def decisions(arm: Path) -> list[dict]:
    f, fz = arm / "pilot_decisions.jsonl", arm / "pilot_decisions.jsonl.gz"
    if f.exists():
        return [json.loads(line) for line in f.open()]
    return [json.loads(line) for line in gzip.open(fz, "rt")] if fz.exists() else []


def main(exp: Path, arms: list[str]) -> None:
    S = {a: json.loads((exp / a / "summary.json").read_text()) for a in arms}
    P = {a: pod_results(exp / a) for a in arms}
    base = arms[0]
    bw, bn = S[base]["wins"], S[base]["games"]

    rows = [("Games / wins", lambda s, a: f"{s['games']} / {s['wins']}"),
            ("Win rate (95% CI)", lambda s, a: "{:.0%} ({:.0%}–{:.0%})".format(s["win_rate"], *wilson(s["wins"], s["games"]))),
            ("Fisher p vs " + base, lambda s, a: "—" if a == base else
             f"{fisher_two_sided(s['wins'], s['games'] - s['wins'], bw, bn - bw):.2f}"),
            ("Draws / timeouts", lambda s, a: str(s["timeouts_or_draws"])),
            ("Avg rounds per game", lambda s, a: str(s["avg_rounds_per_game"])),
            ("Round we die (losses)", lambda s, a: str(s["avg_round_we_died"])),
            ("Round we win", lambda s, a: str(s["avg_round_of_our_win"])),
            ("Commander cast rate / first round", lambda s, a: f"{s['commander_cast_rate']:.0%} / {s['commander_avg_first_round']}"),
            ("Graveyard spells + lands per game", lambda s, a: f"{s['graveyard_spells_per_game']} + {s['graveyard_lands_per_game']}"),
            ("Distinct cards never cast", lambda s, a: str(len(s["never_cast"]))),
            ("How we lost", lambda s, a: ", ".join(f"{k.replace('life total reached 0', 'life')} ×{v}"
                                                   for k, v in s.get("loss_reasons", {}).items()))]
    print("| | " + " | ".join(arms) + " |")
    print("|---" * (len(arms) + 1) + "|")
    for name, fn in rows:
        print(f"| {name} | " + " | ".join(fn(S[a], a) for a in arms) + " |")

    print("\n### Pilot\n")
    for a in arms:
        pl = S[a].get("pilot")
        if not pl:
            continue
        lat = pl.get("latency_ms_avg"), pl.get("latency_ms_p95")
        print(f"- **{a}**: {pl['requests']} requests / {pl['questions']} questions, overruled Forge "
              f"{pl['overrule_rate']:.0%}; Jev latency {lat[0]} ms avg / {lat[1]} p95; Jev ${pl['jev_usd']} "
              f"(${pl['jev_usd'] / max(1, S[a]['games']):.3f}/game)"
              + (f"; {pl['strategist_calls']} memos (avg {pl['strategist_ms_avg']} ms), "
                 f"{pl['escalations']} escalations from {pl['escalation_checks']} checks" if pl.get("strategist_calls") else "")
              + (f"; HOOK ERRORS {pl['hook_errors_logged']}" if pl.get("hook_errors_logged") else ""))
        kinds = sorted(pl["by_kind"].items(), key=lambda kv: -kv[1]["questions"])
        print("  - by kind: " + ", ".join(f"{k} {v['overrules']}/{v['questions']}" for k, v in kinds))

    print("\n### Per pod (same opponents, seat and seed in every arm)\n")
    pods = S[base]["pods"]
    print("| pod | opponents | " + " | ".join(arms) + " |")
    print("|---|---" + "|---" * len(arms) + "|")
    for i, pod in enumerate(pods):
        opp = ", ".join(Path(o).stem.split("-")[0] for o in pod["opponents"])
        cells = []
        for a in arms:
            r = P[a][i] if i < len(P[a]) else []
            cells.append("".join(r) + f" ({r.count('W')})")
        print(f"| {i + 1} | {opp} | " + " | ".join(cells) + " |")

    for a in arms:
        esc = [d for d in decisions(exp / a) if d.get("type") == "escalation"]
        if not esc:
            continue
        kinds = Counter()
        for e in esc:
            for c in e["changes"]:
                kinds[re.sub(r"[:(].*", "", c).strip()] += 1
        print(f"\n### Escalation triggers ({a}, {len(esc)} escalations)\n")
        print(", ".join(f"{k} ×{v}" for k, v in kinds.most_common(12)))


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:])
