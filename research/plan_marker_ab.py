"""Offline A/B: does tagging the memo's planned plays change what Jev picks?

    python3 research/plan_marker_ab.py <pilot_decisions.jsonl> <out.json> [--games pod01,pod02,pod03] [--limit N]

Re-asks Jev, exactly as each logged action decision was posed (state, memo, options, window), twice: as
logged, and with the options the memo's THIS TURN or HOLD line names tagged (edhkit.pilot.plan_marker).
Only decisions with at least one tagged option and a real memo are used. Reports how often Jev's pick is a
planned play, and how often it would clear the margin over Forge's answer, in each arm. Items where the
two arms pick differently are written out, so a blind judge can say which pick was better.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import jev, pilot as P  # noqa: E402

FAILED = re.compile(r"^\s*you've hit your", re.I)


def gate_for(choice: str, default: str) -> float:
    return P.PASS_GATE if choice == "pass" else P.CONFIDENCE_GATE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("out")
    ap.add_argument("--games", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    games = tuple(g for g in args.games.split(",") if g)

    items = []
    for line in open(args.log):
        rec = json.loads(line)
        if rec.get("type") != "decision" or rec.get("kind") != "action" or "state" not in rec:
            continue
        if games and not rec["game"].startswith(games):
            continue
        memo = rec.get("memo") or ""
        if not memo or FAILED.match(memo):
            continue
        q = next((q for q in rec.get("questions", []) if q["id"] == "action"), None)
        if not q:
            continue
        marked = {o["id"] for o in q["options"] if P.plan_marker(memo, o["text"])}
        if marked:
            items.append((rec, q, marked))
    if args.limit:
        items = items[: args.limit]

    pl = P.Pilot.__new__(P.Pilot)
    pl.plan = ""
    pl.provider = jev.get_provider()
    real_marker = P.plan_marker

    def ask(rec, q, with_marks: bool):
        req = {"kind": "action", "game": rec["game"], "state": rec["state"], "questions": [q], **rec.get("context", {})}
        P.plan_marker = real_marker if with_marks else (lambda memo, text: "")
        answers, _ = pl._jev(req, rec["memo"], [], False)
        a = answers.get("action") or {}
        return a.get("choice"), a.get("probabilities") or {}

    def run(item):
        rec, q, marked = item
        default = q.get("default")
        out = {"game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "default": default,
               "planned_ids": sorted(marked), "logged_choice": next(a["choice"] for a in rec["answers"] if a["q"] == "action")}
        for arm, flag in (("plain", False), ("marked", True)):
            try:
                choice, probs = ask(rec, q, flag)
            except Exception as e:  # noqa: BLE001
                out[arm] = {"error": str(e)[:100]}
                continue
            final = choice
            if choice and choice != default and probs.get(choice, 1) - probs.get(default, 0) < gate_for(choice, default):
                final = default
            out[arm] = {"choice": choice, "final": final, "p_choice": round(probs.get(choice, 0), 3),
                        "p_default": round(probs.get(default, 0), 3)}
        text = {o["id"]: o["text"] for o in q["options"]}
        out["labels"] = {k: text.get(v.get("final"), v.get("final"))[:160] for k, v in
                         (("plain", out.get("plain", {})), ("marked", out.get("marked", {})), ("forge", {"final": default}))}
        return out

    # Sequential per item (plan_marker is swapped globally), parallel across items would race; keep it simple.
    results = [run(i) for i in items]
    P.plan_marker = real_marker

    def share(arm, key):
        ok = [r for r in results if "final" in r.get(arm, {})]
        return sum(r[arm][key] in r["planned_ids"] for r in ok), len(ok)

    summary = {}
    for arm in ("plain", "marked"):
        raw_hit, n = share(arm, "choice")
        fin_hit, _ = share(arm, "final")
        summary[arm] = {"decisions": n, "jev_picks_planned": raw_hit, "planned_after_gate": fin_hit}
    changed = [r for r in results if r.get("plain", {}).get("final") != r.get("marked", {}).get("final")]
    summary["final_answer_changed"] = len(changed)
    Path(args.out).write_text(json.dumps({"summary": summary, "changed": changed, "results": results}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
