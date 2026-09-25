"""Paired comparison of two arms run on the same pods and seeds (common random numbers).

    python3 research/paired.py <sim-out A> <sim-out B>

Games are matched by pod and game number. With per-game reseeding (PilotMain), a pair starts from the same
shuffles and stays identical until a decision differs, so the per-game difference in finishing place has
far less noise than two independent samples. Reports the mean difference (B - A; negative = B places
better), its paired standard error next to the unpaired one, and how long each pair stayed identical.
"""
from __future__ import annotations

import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit.scorecard import game_place, pod_games  # noqa: E402

EV = re.compile(r"^(Turn|Add To Stack|Land|Mulligan|Zone Change|Combat|Damage|Resolve Stack)")


def per_game(sim: Path) -> dict:
    """(pod, game) -> (finishing place or None for a draw, the game's events)."""
    return {(pod, g): (game_place(body, us), [re.sub(r"\(\d+\)", "", line) for line in body.splitlines() if EV.match(line)])
            for pod, g, us, body in pod_games(sim)}


def main(a: Path, b: Path) -> None:
    A, B = per_game(a), per_game(b)
    diffs, pa, pb, same_turns = [], [], [], []
    for key in sorted(set(A) & set(B)):
        (x, ea), (y, eb) = A[key], B[key]
        k = next((i for i, (u, v) in enumerate(zip(ea, eb)) if u != v), min(len(ea), len(eb)))
        same_turns.append(sum(1 for line in ea[:k] if line.startswith("Turn")))
        if x is None or y is None:
            continue
        diffs.append(y - x)
        pa.append(x)
        pb.append(y)
    n = len(diffs)
    if n < 2:
        print("not enough paired games")
        return
    paired_se = st.stdev(diffs) / n ** 0.5
    unpaired_se = (st.variance(pa) / n + st.variance(pb) / n) ** 0.5
    corr = st.correlation(pa, pb) if len(set(pa)) > 1 and len(set(pb)) > 1 else float("nan")
    print(f"{n} paired games (draws dropped)")
    print(f"avg place: {a.name} {st.mean(pa):.2f}, {b.name} {st.mean(pb):.2f}; "
          f"difference (B - A) {st.mean(diffs):+.2f}")
    print(f"standard error: paired {paired_se:.2f}, unpaired {unpaired_se:.2f}; place correlation {corr:.2f}")
    print(f"turns the pair stayed identical: median {st.median(same_turns)}, "
          f"identical from the start of turn 1 in {sum(1 for t in same_turns if t >= 1)} of {len(same_turns)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
