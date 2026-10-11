"""A/B the pilot's executor model on logged decisions: Jev vs a Claude model (Haiku 5.5 by default).

    python3 research/executor_ab.py --n 70 --judge 90 --out research/<dir>

For each sampled decision of each piloted run (needs --log-state logs), both executors answer the same request
through the same sidecar: same board, memo, memo age, options, plan tags and gates. Only the provider differs.
We record each model's raw pick (before the gates) and the final answer, and a blind Opus judge (memo hidden,
answers in random order) compares the two final answers wherever they differ. No games are played.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edhkit import pilot as P, pilot_audit, replay  # noqa: E402
from edhkit.llm_executor import ClaudeExecutorProvider  # noqa: E402

RUNS = [  # (piloted run, the deck it piloted)
    ("decks/obeka-splitter-of-seconds/many-mornings/sims/validate-r1", "decks/obeka-splitter-of-seconds/many-mornings/deck.txt"),
    ("decks/obeka-splitter-of-seconds/long-morning/sims/validate-r3", "decks/obeka-splitter-of-seconds/long-morning/deck.txt"),
    ("decks/obeka-splitter-of-seconds/twice-told/sims/validate-r4", "decks/obeka-splitter-of-seconds/twice-told/deck.txt"),
]
KINDS = {"action", "attack", "block", "trigger-target", "choose", "discard", "search", "target", "optional-trigger"}

_local = threading.local()
_claude_providers: list = []  # for the usage and cost summary


class Recording:
    """Wraps a provider and keeps its raw answers per decision (keyed by the thread's current decision)."""

    def __init__(self, inner):
        self.inner, self.raw, self.ms = inner, {}, {}
        self.usage = getattr(inner, "usage", {})

    def evaluate(self, state, questions, progress=""):
        t0 = time.time()
        ans = self.inner.evaluate(state, questions, progress)
        self.raw[_local.key] = {q: a for q, a in ans.items() if q != "__escalate"}
        self.ms[_local.key] = int((time.time() - t0) * 1000)
        return ans


def run_one(sim: Path, deck: Path, n: int, seed: int, model: str, effort: str, workers: int,
            transport: str = "auto") -> list[dict]:
    plan = P.deck_plan(deck.parent / "brief.md", deck.parent / "notes.md")
    recs = [r for r in replay._records(sim, KINDS)
            if any(len(q.get("options", [])) >= 2 for q in r["questions"])]
    recs = random.Random(seed).sample(recs, min(n, len(recs)))
    pilots = {}
    for name in ("jev", "claude"):
        p = P.Pilot(plan, strategist="static", escalate=False, deck_path=deck)
        if name == "claude":
            _claude_providers.append(ClaudeExecutorProvider(model, effort, transport))
        p.provider = Recording(p.provider if name == "jev" else _claude_providers[-1])
        pilots[name] = p

    def ask(name, i, rec):
        p = pilots[name]
        key = f"{rec['game']}#{i}"
        _local.key = key
        g = p._game(key)
        g.update(memo=rec.get("memo") or "", our_turns=rec.get("memo_age") or 0, memo_our_turn=0, turn=rec.get("turn"))
        req = {"game": key, "kind": rec["kind"], "state": rec["state"], "questions": rec["questions"],
               **rec.get("context", {})}
        try:
            return p.ask(req)["answers"], p.provider.raw.get(key, {}), p.provider.ms.get(key)
        except Exception as e:  # noqa: BLE001
            return None, {}, str(e)[:120]

    def both(i_rec):
        i, rec = i_rec
        return rec, ask("jev", i, rec), ask("claude", i, rec)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(both, enumerate(recs)))

    rows = []
    for rec, (jf, jr, jms), (cf, cr, cms) in results:
        if jf is None or cf is None:
            rows.append({"game": rec["game"], "turn": rec["turn"], "kind": rec["kind"], "error": str(jms if jf is None else cms)})
            continue
        for q in rec["questions"]:
            if len(q.get("options", [])) < 2 or q["id"] not in jf or q["id"] not in cf:
                continue
            text = {o["id"]: o["text"] for o in q["options"]}
            default = next((a["default"] for a in rec["answers"] if a["q"] == q["id"]), q.get("default"))
            rows.append({
                "sim": str(sim), "game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "kind": rec["kind"],
                "prompt": q["prompt"], "n_options": len(q["options"]),
                "default": text.get(default, default),
                "jev_final": text.get(jf[q["id"]], jf[q["id"]]), "claude_final": text.get(cf[q["id"]], cf[q["id"]]),
                "jev_raw": text.get((jr.get(q["id"]) or {}).get("choice"), None),
                "claude_raw": text.get((cr.get(q["id"]) or {}).get("choice"), None),
                "claude_answered": q["id"] in cr,
                "jev_ms": jms, "claude_ms": cms,
                "state": rec["state"], "memo": rec.get("memo", ""), "context": rec.get("context", {}), "plan": plan})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=70, help="decisions sampled per run")
    ap.add_argument("--judge", type=int, default=90, help="max final-answer disagreements to judge")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--transport", default="auto", choices=["auto", "api", "cli"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for sim, deck in RUNS:
        rows += run_one(ROOT / sim, ROOT / deck, a.n, a.seed, a.model, a.effort, a.workers, a.transport)
    ok = [r for r in rows if "error" not in r]
    agree_final = sum(r["jev_final"] == r["claude_final"] for r in ok)
    agree_raw = sum(r["jev_raw"] == r["claude_raw"] for r in ok if r["jev_raw"] and r["claude_raw"])
    raw_n = sum(1 for r in ok if r["jev_raw"] and r["claude_raw"])
    claude_missing = sum(not r["claude_answered"] for r in ok)

    # judge final-answer disagreements, per deck plan; "pilot" = the Claude model's answer, "forge" = Jev's
    diff = [r for r in ok if r["jev_final"] != r["claude_final"]]
    rng = random.Random(a.seed)
    rng.shuffle(diff)
    diff = diff[:a.judge]
    tally, by_kind, verdicts = Counter(), {}, []
    for plan in sorted({r["plan"] for r in diff}):
        items = [{**r, "pilot": r["claude_final"], "forge": r["jev_final"]} for r in diff if r["plan"] == plan]
        j = pilot_audit.audit_items(items, plan, n=len(items), seed=a.seed, workers=2, hide_memo=True)
        tally.update(j["tally"])
        for k, v in j["by_kind"].items():
            by_kind.setdefault(k, Counter()).update(v)
        verdicts += j["results"]
    decided = tally["pilot"] + tally["forge"]
    summary = {
        "model": a.model, "effort": a.effort, "decisions_answered": len(ok), "errors": len(rows) - len(ok),
        "claude_failed_or_unparsed": claude_missing,
        "agree_final": f"{agree_final}/{len(ok)}", "agree_raw": f"{agree_raw}/{raw_n}",
        "disagreements_judged": len(diff),
        "judge_tally": {"claude_better": tally["pilot"], "jev_better": tally["forge"], "same": tally["same"],
                        "unparsed": tally["unparsed"]},
        "claude_share_of_decided": round(tally["pilot"] / decided, 3) if decided else None,
        "sign_test_p": round(pilot_audit.sign_test(tally["pilot"], decided), 4),
        "by_kind": {k: {"claude": v["pilot"], "jev": v["forge"], "same": v["same"]} for k, v in by_kind.items()},
        "median_ms": {"jev": sorted(r["jev_ms"] for r in ok if isinstance(r["jev_ms"], int))[len(ok) // 2] if ok else None,
                      "claude": sorted(r["claude_ms"] for r in ok if isinstance(r["claude_ms"], int))[len(ok) // 2] if ok else None},
    }
    usage = Counter()
    for pr in _claude_providers:
        usage.update(pr.usage)
    summary["claude_transport"] = _claude_providers[0].transport if _claude_providers else None
    summary["claude_usage"] = dict(usage)
    summary["claude_usd"] = round(sum(pr.cost_usd() for pr in _claude_providers), 4)
    summary["claude_usd_per_request"] = round(summary["claude_usd"] / usage["requests"], 5) if usage["requests"] else None
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "verdicts.json").write_text(json.dumps(verdicts, indent=1))
    (out / "rows.jsonl").write_text("\n".join(json.dumps({k: v for k, v in r.items() if k not in ("state", "plan")})
                                              for r in rows))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
