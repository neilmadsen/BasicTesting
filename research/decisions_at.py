"""Print every pilot decision for one game and a turn range, with all options offered.

    python3 research/decisions_at.py <pilot_decisions.jsonl> pod03-g2 45 49

Needs a --log-state pilot log (options and memos are only logged then).

Marks per option: F = Forge's own answer (the default), J = what Jev preferred (raw, before the margin
gate), -> = the answer actually used. 'gated' means Jev preferred another option but under the margin, so
Forge's answer stood. Memos are printed when they were (re)written in the range.
"""
import gzip, json, sys
LOG = sys.argv[1]
game, t0, t1 = sys.argv[2], int(sys.argv[3]), int(sys.argv[4] if len(sys.argv) > 4 else sys.argv[3])
for line in (gzip.open(LOG, "rt") if LOG.endswith(".gz") else open(LOG)):
    d = json.loads(line)
    if d.get("game") != game or not (t0 <= (d.get("turn") or 0) <= t1):
        continue
    if d["type"] == "memo":
        print(f"\n=== MEMO turn {d['turn']} ({d.get('reason','')[:100]}):\n{d['memo'].strip()[:1500]}\n")
        continue
    if d["type"] == "escalation":
        print(f"--- escalation turn {d['turn']} p={d['p']}: {'; '.join(d['changes'])[:200]}")
        continue
    if d["type"] != "decision":
        continue
    ctx = d.get("context", {})
    print(f"[t{d['turn']} {d['phase']} {d['kind']}{' ESCALATED' if d['escalated'] else ''}] {ctx.get('window','')[:120]} {('stack: '+str(ctx.get('stack_top'))[:100]) if ctx.get('stack_top') else ''}")
    ans = {a["q"]: a for a in d["answers"]}
    for q in d.get("questions", []):
        a = ans.get(q["id"], {})
        if a.get("unused"):
            continue
        raw = a.get("raw_choice", a.get("choice"))
        flag = " (gated, margin %s)" % a.get("margin") if a.get("gated") else (" (OVERRULE)" if a.get("choice") != a.get("default") else "")
        print(f"   Q {q['id']}: {q['prompt'][:140]}{flag}")
        for o in q["options"]:
            m = ("F" if o["id"] == a.get("default") else " ") + ("J" if o["id"] == raw else " ") + ("->" if o["id"] == a.get("choice") else "  ")
            print(f"     {m} {o['text'][:160]}")
