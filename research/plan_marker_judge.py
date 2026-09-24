"""Blind-judge the decisions the plan tags changed (see plan_marker_ab.py).

    python3 research/plan_marker_judge.py <pilot_decisions.jsonl> <plan_marker_ab.json> <deck-dir> <out.json>

For each decision where the tags moved Jev's final answer from an unplanned option to a planned one, an Opus
judge (memo hidden) compares the two picks on the logged board. 'pilot' = the tagged (plan-following) pick,
'forge' = the untagged pick.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import pilot as P, pilot_audit as A  # noqa: E402

log, ab, deck_dir, out = sys.argv[1:5]
failed = re.compile(r"^\s*you've hit your", re.I)
recs = []
for line in open(log):
    rec = json.loads(line)
    if rec.get("type") != "decision" or rec.get("kind") != "action" or "state" not in rec:
        continue
    memo = rec.get("memo") or ""
    q = next((q for q in rec.get("questions", []) if q["id"] == "action"), None)
    if memo and not failed.match(memo) and q and any(P.plan_marker(memo, o["text"]) for o in q["options"]):
        recs.append((rec, q))
results = json.load(open(ab))["results"]
assert len(results) == len(recs), "the A/B file must come from the same log"
items = []
for r, (rec, q) in zip(results, recs):
    pl, mk, planned = r["plain"].get("final"), r["marked"].get("final"), set(r["planned_ids"])
    if pl == mk or mk not in planned or pl in planned:
        continue
    text = {o["id"]: o["text"] for o in q["options"]}
    items.append({"game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "kind": "action",
                  "prompt": q["prompt"], "forge": text[pl], "pilot": text[mk], "state": rec["state"],
                  "memo": rec.get("memo", ""), "context": rec.get("context", {})})
root = Path(deck_dir)
res = A.audit_items(items, P.deck_plan(root / "brief.md", root / "notes.md"), n=len(items), workers=2, hide_memo=True)
Path(out).write_text(json.dumps(res, indent=1))
print(A.report(res))
