"""Blind decision audit: were the pilot's overrules better than Forge's own choices?

Win rates need hundreds of games to separate two pilots. Decisions are far more
plentiful: every overrule is a paired comparison on an identical board. This
samples overrules from a pilot log written with EDH_PILOT_LOG_STATE=1, shows a
judge model the deck plan, the strategy memo, the board and the two candidate
answers in random order (it is not told which one is Forge's), and tallies
which it prefers. A sign test on pilot-better vs Forge-better gives the p-value.

Caveat: the default judge is the same model family as the strategist, so it may
share the strategist's biases. It judges single decisions, not whole games.
"""
from __future__ import annotations

import json
import math
import random
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

JUDGE_SYSTEM = (
    "You are an expert Magic: The Gathering Commander player judging one decision in a four-player game. "
    "You get our deck plan, our current strategy memo, the board as JSON (with oracle text), the decision, "
    "and two candidate answers, A and B. Decide which is the better play for our side from this exact "
    "position, thinking a few turns ahead. Reply with one line: A, B, or SAME (if neither is clearly "
    "better), then ' — ' and a reason of at most 25 words."
)


def load_overrules(log: Path) -> list[dict]:
    items = []
    for line in log.open():
        rec = json.loads(line)
        if rec.get("type") != "decision" or "state" not in rec:
            continue
        qs = {q["id"]: q for q in rec.get("questions", [])}
        for a in rec["answers"]:
            if a.get("unused") or a["choice"] == a["default"] or a["q"] not in qs:
                continue
            q = qs[a["q"]]
            text = {o["id"]: o["text"] for o in q["options"]}
            if a["choice"] not in text or a["default"] not in text:
                continue
            items.append({"game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "kind": rec["kind"],
                          "prompt": q["prompt"], "forge": text[a["default"]], "pilot": text[a["choice"]],
                          "state": rec["state"], "memo": rec.get("memo", ""), "context": rec.get("context", {})})
    return items


def _prompt(item: dict, plan: str, pilot_is_a: bool) -> str:
    a, b = (item["pilot"], item["forge"]) if pilot_is_a else (item["forge"], item["pilot"])
    ctx = "".join(f"\n{k}: {v}" for k, v in item["context"].items())
    return (f"Deck plan:\n{plan}\n\nStrategy memo:\n{item['memo'] or '(none)'}\n\n"
            f"Board (JSON):\n{json.dumps(item['state'], ensure_ascii=False)}\n\n"
            f"Decision ({item['kind']}, turn {item['turn']}, {item['phase']}):{ctx}\n{item['prompt']}\n\n"
            f"A: {a}\nB: {b}\n\nWhich is better?")


def _judge(prompt: str, model: str, effort: str) -> str:
    out = subprocess.run(
        ["claude", "-p", "--tools", "", "--no-session-persistence", "--effort", effort,
         "--model", model, "--system-prompt", JUDGE_SYSTEM],
        input=prompt, capture_output=True, text=True, timeout=300, cwd=tempfile.gettempdir())
    return out.stdout.strip()


def sign_test(k: int, n: int) -> float:
    """Two-sided exact binomial test of k successes in n trials at p = 0.5."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def audit(log: Path, plan: str, n: int = 60, seed: int = 1, model: str = "claude-opus-5-5",
          effort: str = "medium", workers: int = 4, kinds: set[str] | None = None) -> dict:
    items = load_overrules(log)
    if kinds:
        items = [i for i in items if i["kind"] in kinds]
    rng = random.Random(seed)
    sample = rng.sample(items, min(n, len(items)))
    order = [rng.random() < 0.5 for _ in sample]

    def run(k: int) -> dict:
        item, pilot_is_a = sample[k], order[k]
        try:
            reply = _judge(_prompt(item, plan, pilot_is_a), model, effort)
        except Exception as e:  # a judge failure is recorded, not fatal
            reply = f"ERROR {e}"
        m = re.match(r"\W*(A|B|SAME)\b", reply, re.I)
        verdict = "unparsed"
        if m:
            v = m.group(1).upper()
            verdict = "same" if v == "SAME" else "pilot" if (v == "A") == pilot_is_a else "forge"
        return {"kind": item["kind"], "game": item["game"], "turn": item["turn"], "forge": item["forge"][:140],
                "pilot": item["pilot"][:140], "verdict": verdict, "reply": reply[:300]}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run, range(len(sample))))
    tally = Counter(r["verdict"] for r in results)
    by_kind: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_kind[r["kind"]][r["verdict"]] += 1
    decided = tally["pilot"] + tally["forge"]
    return {"log": str(log), "overrules_available": len(items), "sampled": len(sample), "judge": model,
            "effort": effort, "tally": dict(tally), "pilot_share_of_decided": round(tally["pilot"] / decided, 3)
            if decided else None, "sign_test_p": round(sign_test(tally["pilot"], decided), 4),
            "by_kind": {k: dict(v) for k, v in by_kind.items()}, "results": results}


def report(res: dict) -> str:
    t = res["tally"]
    L = [f"Audit of {res['sampled']} of {res['overrules_available']} overrules ({res['judge']}, effort {res['effort']}):",
         f"  pilot better {t.get('pilot', 0)}, Forge better {t.get('forge', 0)}, same {t.get('same', 0)}, "
         f"unparsed {t.get('unparsed', 0)}  →  pilot wins {res['pilot_share_of_decided']} of decided "
         f"(sign test p = {res['sign_test_p']})"]
    for k, v in sorted(res["by_kind"].items(), key=lambda kv: -sum(kv[1].values())):
        L.append(f"    {k}: pilot {v.get('pilot', 0)} / Forge {v.get('forge', 0)} / same {v.get('same', 0)}")
    for verdict in ("forge", "pilot"):
        ex = [r for r in res["results"] if r["verdict"] == verdict][:3]
        if ex:
            L.append(f"  examples where {'Forge' if verdict == 'forge' else 'the pilot'} was judged better:")
            for r in ex:
                L.append(f"    - [{r['kind']} t{r['turn']}] pilot: {r['pilot'][:70]} | Forge: {r['forge'][:70]}")
                L.append(f"      judge: {r['reply'][:160]}")
    return "\n".join(L)
