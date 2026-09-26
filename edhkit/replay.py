"""Replay a piloted run's decisions through the current executor, without playing any games.

    ./edh replay <sim-out> --deck deck.txt [--kinds action,attack] [--limit N] [--judge N]

Every logged decision (needs a --log-state log) is re-asked exactly as it was posed: same board, memo, memo
age, options and window, with the sidecar as it is now (guidance, margins, plan tags, memo handling). The
report says how many final answers change, by decision kind, with examples. --judge N has a blind Opus
judge (memo hidden) compare the old and new answer on N of the changed decisions.

This is the fast loop for executor changes made in Python. Changes to the Java side (which options exist,
their labels) need new games: their effect isn't in an old log.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import pilot as P
from .scorecard import _log, _open


def _records(sim: Path, kinds: set[str] | None) -> list[dict]:
    out = []
    for line in _open(_log(sim)):
        d = json.loads(line)
        if d.get("type") != "decision" or "state" not in d or not d.get("questions"):
            continue
        if kinds and d["kind"] not in kinds:
            continue
        out.append(d)
    return out


def replay(sim: Path, plan: str, kinds: set[str] | None = None, limit: int = 0, seed: int = 1,
           workers: int = 8, steer: bool = False) -> dict:
    recs = _records(sim, kinds)
    if limit and len(recs) > limit:
        recs = random.Random(seed).sample(recs, limit)
    pilot = P.Pilot(plan, strategist="static", escalate=False, steer=steer)

    def run(i_rec):
        i, rec = i_rec
        key = f"{rec['game']}#{i}"  # one private game state per decision, so decisions can run in parallel
        g = pilot._game(key)
        g.update(memo=rec.get("memo") or "", our_turns=rec.get("memo_age") or 0, memo_our_turn=0,
                 turn=rec.get("turn"))
        req = {"game": key, "kind": rec["kind"], "state": rec["state"], "questions": rec["questions"],
               **rec.get("context", {})}
        try:
            new = pilot.ask(req)["answers"]
        except Exception as e:  # noqa: BLE001
            return rec, None, str(e)[:120]
        return rec, new, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run, enumerate(recs)))

    changed, errors, by_kind = [], 0, defaultdict(Counter)
    for rec, new, err in results:
        if err:
            errors += 1
            continue
        qs = {q["id"]: q for q in rec["questions"]}
        for a in rec["answers"]:
            if a.get("unused") or a["q"] not in new or a["q"] not in qs:
                continue
            by_kind[rec["kind"]]["answers"] += 1
            old_c, new_c = a["choice"], new[a["q"]]
            if old_c == new_c:
                continue
            q = qs[a["q"]]
            text = {o["id"]: o["text"] for o in q["options"]}
            by_kind[rec["kind"]]["changed"] += 1
            by_kind[rec["kind"]]["now matches Forge" if new_c == a["default"] else "now differs from Forge"] += 1
            changed.append({"game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "kind": rec["kind"],
                            "prompt": q["prompt"], "old": text.get(old_c, old_c), "new": text.get(new_c, new_c),
                            "forge": text.get(a["default"], a["default"]), "state": rec["state"],
                            "memo": rec.get("memo", ""), "context": rec.get("context", {})})
    return {"decisions": len(recs), "errors": errors, "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
            "changed": changed}


def judge(res: dict, plan: str, n: int, seed: int = 1) -> dict:
    """Blind judge on n changed answers: 'pilot' = the new answer, 'forge' = the old one."""
    from . import pilot_audit
    items = [{**c, "pilot": c["new"], "forge": c["old"]} for c in res["changed"]]
    return pilot_audit.audit_items(items, plan, n=n, seed=seed, workers=2, hide_memo=True)


def report(res: dict, examples: int = 8) -> str:
    lines = [f"replayed {res['decisions']} decisions ({res['errors']} errors)"]
    for kind, c in res["by_kind"].items():
        n, ch = c.get("answers", 0), c.get("changed", 0)
        lines.append(f"  {kind:<16} {ch:>4} of {n:>5} answers changed"
                     + (f" ({c.get('now matches Forge', 0)} back to Forge's, {c.get('now differs from Forge', 0)} "
                        f"away from it)" if ch else ""))
    for c in res["changed"][:examples]:
        lines.append(f"  - {c['game']} t{c['turn']} {c['kind']}: {c['old'][:70]}  ->  {c['new'][:70]}")
    return "\n".join(lines)
