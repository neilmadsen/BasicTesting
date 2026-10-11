"""A/B two executor arms on logged decisions, with a blind judge where they disagree.

    python3 research/executor_ab.py --a jev --b haiku --n 70 --judge 90 --out research/<dir>
    python3 research/executor_ab.py --a haiku --b haiku+log --n 70 --judge 90 --out research/<dir>

An arm is `jev`, `haiku` or `sonnet`, optionally with `+log` (the executor also gets the round-by-round game
digest from edhkit/gamelog.py, rebuilt from every earlier logged state of that game). For each sampled
decision of each piloted run (needs --log-state logs), both arms answer the same request through the same
sidecar: same board, memo, memo age, options, plan tags and gates. We record each arm's raw pick (before the
gates) and final answer. A blind Opus judge (memo hidden, answers in random order, the game digest shown
whenever either arm had it) compares the final answers where they differ. "pilot" in the judge's terms is
arm B, the challenger. No games are played.
"""
from __future__ import annotations

import argparse
import copy
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

from edhkit import pilot as P, pilot_audit  # noqa: E402
from edhkit.gamelog import GameLog  # noqa: E402
from edhkit.llm_executor import ClaudeExecutorProvider  # noqa: E402
from edhkit.scorecard import _log, _open  # noqa: E402

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


def sample_with_logs(sim: Path, n: int, seed: int) -> list[tuple[dict, GameLog]]:
    """Sampled decision records, each with the game digest built from every earlier state of its game."""
    lines = list(_open(_log(sim)))
    cands = []
    for i, line in enumerate(lines):
        d = json.loads(line)
        if (d.get("type") == "decision" and "state" in d and d.get("questions") and d["kind"] in KINDS
                and any(len(q.get("options", [])) >= 2 for q in d["questions"])):
            cands.append(i)
    chosen = set(random.Random(seed).sample(cands, min(n, len(cands))))
    logs: dict[str, GameLog] = {}
    out = []
    for i, line in enumerate(lines):
        d = json.loads(line)
        if not isinstance(d.get("state"), dict):
            continue
        g = logs.setdefault(d.get("game"), GameLog())
        if i in chosen:
            out.append((d, copy.deepcopy(g)))  # before this state: the pilot adds it when it asks
        g.update(d["state"])
    return out


def make_arm(spec: str, plan: str, deck: Path, effort: str, transport: str) -> P.Pilot:
    name, _, flag = spec.partition("+")
    p = P.Pilot(plan, strategist="static", escalate=False, deck_path=deck, game_log=(flag == "log"))
    if name != "jev":
        _claude_providers.append(ClaudeExecutorProvider(P.EXECUTOR_MODELS[name], effort, transport))
        p.provider = _claude_providers[-1]
    p.provider = Recording(p.provider)
    return p


def run_one(sim: Path, deck: Path, arms: tuple[str, str], n: int, seed: int, effort: str, workers: int,
            transport: str) -> list[dict]:
    plan = P.deck_plan(deck.parent / "brief.md", deck.parent / "notes.md")
    recs = sample_with_logs(sim, n, seed)
    pilots = {arm: make_arm(arm, plan, deck, effort, transport) for arm in arms}

    def ask(arm, i, rec, glog):
        p = pilots[arm]
        key = f"{rec['game']}#{i}"
        _local.key = key
        g = p._game(key)
        g.update(memo=rec.get("memo") or "", our_turns=rec.get("memo_age") or 0, memo_our_turn=0, turn=rec.get("turn"))
        if p.game_log:
            g["gamelog"] = copy.deepcopy(glog)
        req = {"game": key, "kind": rec["kind"], "state": rec["state"], "questions": rec["questions"],
               **rec.get("context", {})}
        try:
            return p.ask(req)["answers"], p.provider.raw.get(key, {}), p.provider.ms.get(key)
        except Exception as e:  # noqa: BLE001
            return None, {}, str(e)[:120]

    def both(i_rec):
        i, (rec, glog) = i_rec
        return rec, glog, ask(arms[0], i, rec, glog), ask(arms[1], i, rec, glog)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(both, enumerate(recs)))

    any_log = any(a.endswith("+log") for a in arms)
    rows = []
    for rec, glog, (af, ar, ams), (bf, br, bms) in results:
        if af is None or bf is None:
            rows.append({"game": rec["game"], "turn": rec["turn"], "kind": rec["kind"], "error": str(ams if af is None else bms)})
            continue
        state = dict(rec["state"])
        if any_log:  # the judge sees what the arms saw
            g2 = copy.deepcopy(glog)
            g2.update(rec["state"])
            done, now = g2.rounds(rec["state"].get("turn"))
            state["game_log"] = {"completed_rounds": done, "this_round": now}
        for q in rec["questions"]:
            if len(q.get("options", [])) < 2 or q["id"] not in af or q["id"] not in bf:
                continue
            text = {o["id"]: o["text"] for o in q["options"]}
            default = next((a["default"] for a in rec["answers"] if a["q"] == q["id"]), q.get("default"))
            rows.append({
                "sim": str(sim), "game": rec["game"], "turn": rec["turn"], "phase": rec["phase"], "kind": rec["kind"],
                "prompt": q["prompt"], "n_options": len(q["options"]), "default": text.get(default, default),
                "a_final": text.get(af[q["id"]], af[q["id"]]), "b_final": text.get(bf[q["id"]], bf[q["id"]]),
                "a_raw": text.get((ar.get(q["id"]) or {}).get("choice")),
                "b_raw": text.get((br.get(q["id"]) or {}).get("choice")),
                "b_answered": q["id"] in br, "a_ms": ams, "b_ms": bms,
                "state": state, "memo": rec.get("memo", ""), "context": rec.get("context", {}), "plan": plan})
    return rows


def _median(xs):
    xs = sorted(x for x in xs if isinstance(x, int))
    return xs[len(xs) // 2] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="jev", help="baseline arm: jev | haiku | sonnet, optionally +log")
    ap.add_argument("--b", default="haiku", help="challenger arm, same syntax")
    ap.add_argument("--n", type=int, default=70, help="decisions sampled per run")
    ap.add_argument("--judge", type=int, default=90, help="max final-answer disagreements to judge")
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
        rows += run_one(ROOT / sim, ROOT / deck, (a.a, a.b), a.n, a.seed, a.effort, a.workers, a.transport)
    ok = [r for r in rows if "error" not in r]
    agree_final = sum(r["a_final"] == r["b_final"] for r in ok)
    raw_pairs = [r for r in ok if r["a_raw"] and r["b_raw"]]

    diff = [r for r in ok if r["a_final"] != r["b_final"]]
    random.Random(a.seed).shuffle(diff)
    diff = diff[:a.judge]
    tally, by_kind, verdicts = Counter(), {}, []
    for plan in sorted({r["plan"] for r in diff}):
        items = [{**r, "pilot": r["b_final"], "forge": r["a_final"]} for r in diff if r["plan"] == plan]
        j = pilot_audit.audit_items(items, plan, n=len(items), seed=a.seed, workers=2, hide_memo=True)
        tally.update(j["tally"])
        for k, v in j["by_kind"].items():
            by_kind.setdefault(k, Counter()).update(v)
        verdicts += j["results"]
    decided = tally["pilot"] + tally["forge"]
    usage = Counter()
    for pr in _claude_providers:
        usage.update({k: v for k, v in pr.usage.items() if isinstance(v, (int, float))})
    summary = {
        "a": a.a, "b": a.b, "effort": a.effort, "decisions_answered": len(ok), "errors": len(rows) - len(ok),
        "b_failed_or_unparsed": sum(not r["b_answered"] for r in ok),
        "agree_final": f"{agree_final}/{len(ok)}",
        "agree_raw": f"{sum(r['a_raw'] == r['b_raw'] for r in raw_pairs)}/{len(raw_pairs)}",
        "disagreements": len([r for r in ok if r["a_final"] != r["b_final"]]), "judged": len(diff),
        "judge_tally": {"b_better": tally["pilot"], "a_better": tally["forge"], "same": tally["same"],
                        "unparsed": tally["unparsed"]},
        "b_share_of_decided": round(tally["pilot"] / decided, 3) if decided else None,
        "sign_test_p": round(pilot_audit.sign_test(tally["pilot"], decided), 4),
        "by_kind": {k: {"b": v["pilot"], "a": v["forge"], "same": v["same"]} for k, v in by_kind.items()},
        "median_ms": {"a": _median(r["a_ms"] for r in ok), "b": _median(r["b_ms"] for r in ok)},
        "claude_transport": _claude_providers[0].transport if _claude_providers else None,
        "claude_usage": dict(usage),
        "claude_usd": round(sum(pr.cost_usd() for pr in _claude_providers), 4),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "verdicts.json").write_text(json.dumps(verdicts, indent=1))
    (out / "rows.jsonl").write_text("\n".join(json.dumps({k: v for k, v in r.items() if k not in ("state", "plan")})
                                              for r in rows))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
