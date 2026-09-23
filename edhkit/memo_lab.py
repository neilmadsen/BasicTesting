"""Memo lab: how good are the strategist's memos, and what are they missing?

Works offline on a pilot log written with --log-state. Each memo is paired
with the board it was written on (the next logged decision in that game).

- critique: an expert reviewer sees the strategist's exact prompt, its memo, and
  (clearly marked) extra information the strategist did not have: the real
  decklist and card text. It scores the memo against how a top player thinks,
  separates reasoning failures from information gaps, and writes the memo it
  would have written.
- ab: regenerate memos for the same boards under a different strategist setup,
  then have a blind judge compare old and new, A/B in random order.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUBRIC = {
    "threat": "Threat assessment by trajectory: who wins soonest if unchecked, which commanders and engines "
              "are answer-on-sight (and whether killing the commander actually stops it), not just the biggest "
              "creature on board.",
    "answers": "Interaction budget: which of our answers (in hand, recursive in the graveyard, tutorable) are "
               "earmarked for which threats; renewable answers spent freely, one-shot answers saved.",
    "target_state": "Proactive plan: the board state our deck is trying to reach (engine online, lanes stocked, "
                    "protection up), what is missing, and the fastest safe path over the next 2-3 turns.",
    "win_path": "How we actually close from here, and our clock compared with the opponents' clocks.",
    "risk": "Risk management: wipe and graveyard-hate exposure, protecting key pieces, not overextending, "
            "holding back what should be held.",
    "sequencing": "Concrete, executable sequencing this turn: mana use, land drops, instant-speed plays on "
                  "others' turns, correct card and rules use.",
}

CRITIC_SYSTEM = (
    "You are a world-class Commander (EDH) player and coach. An AI strategist writes a short memo each turn "
    "for a fast executor model that makes every in-game decision for our seat in a four-player game. You "
    "review one memo. You see exactly what the strategist saw, then EXTRA INFORMATION it did not have.\n\n"
    "Score the memo 0-3 on each dimension (0 = absent or wrong, 1 = weak, 2 = solid, 3 = what a top player "
    "would write):\n"
    + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    + "\n\nThen say what the memo most importantly missed, and for each shortcoming whether it is a "
    "REASONING failure (the strategist had the information) or an INFORMATION gap (it needed something it "
    "was not given; name exactly what). Note factual or rules errors. Finally write the memo you would "
    "have written, in the same format and word budget as the memo under review.\n\n"
    "Reply with only a JSON object:\n"
    '{"scores": {"threat": n, "answers": n, "target_state": n, "win_path": n, "risk": n, "sequencing": n}, '
    '"biggest_miss": "...", '
    '"shortcomings": [{"what": "...", "type": "reasoning" | "information", "missing_info": "... or null", '
    '"info_category": "opponent_deck_knowledge" | "our_decklist" | "game_history" | "card_text" | '
    '"opponent_resources" | "turn_order" | "other" | null}], '
    '"errors": ["..."], "ideal_memo": "..."}'
)

AB_SYSTEM = (
    "You are a world-class Commander (EDH) player. Two strategy memos, A and B, were written for the same "
    "board by different strategists. A fast executor model will follow the memo for every decision this "
    "turn. Judge which memo would lead to better play from this exact position, considering threat "
    "assessment, how answers are budgeted, the target board state, the win path, risk, and concrete "
    "sequencing. Penalise factual or rules errors. Longer is not better in itself: the executor must be able "
    "to follow the memo. Reply with one line: A, B or SAME, then ' — ' and at most 40 words of reasons."
)


# --------------------------------------------------------------------------- data

def load_memo_points(log: Path) -> list[dict]:
    """Every memo with the board it was written on, the previous memo, and the reason."""
    points, pending, last_memo = [], {}, {}
    for line in log.open():
        rec = json.loads(line)
        game = rec.get("game")
        if rec.get("type") == "memo":
            rec["previous_memo"] = last_memo.get(game, "")
            last_memo[game] = rec.get("memo", "")
            pending[game] = rec
        elif rec.get("type") == "decision" and "state" in rec and game in pending:
            m = pending.pop(game)
            points.append({"game": game, "turn": m["turn"], "reason": m["reason"], "memo": m["memo"],
                           "previous_memo": m["previous_memo"], "state": rec["state"]})
    return [p for p in points if p["memo"]]


def sample_points(points: list[dict], n: int, seed: int = 1) -> list[dict]:
    """Stratified: early (rounds 1-3), mid (4-7), late (8+), and escalation re-plans."""
    def stratum(p):
        if "escalation" in p["reason"]:
            return "escalation"
        rnd = (p["turn"] + 3) // 4
        return "early" if rnd <= 3 else "mid" if rnd <= 7 else "late"
    buckets = defaultdict(list)
    for p in points:
        buckets[stratum(p)].append(p)
    rng = random.Random(seed)
    for b in buckets.values():
        rng.shuffle(b)
    out, keys = [], sorted(buckets)
    while len(out) < n and any(buckets.values()):
        for k in keys:
            if buckets[k] and len(out) < n:
                p = buckets[k].pop()
                p["stratum"] = k
                out.append(p)
    return out


def strategist_prompt(plan: str, point: dict) -> str:
    """The exact prompt the strategist received (see Pilot._refresh)."""
    board = json.dumps({k: v for k, v in point["state"].items() if k != "card_text"}, ensure_ascii=False)
    return (f"Deck plan:\n{plan}\n\nCurrent board (JSON):\n{board}\n\n"
            f"Previous memo:\n{point['previous_memo'] or '(none)'}\n\nReason for this memo: {point['reason']}\n\n"
            "Write the new memo.")


def _claude(system: str, prompt: str, model: str, effort: str, timeout: int = 600) -> str:
    out = subprocess.run(
        ["claude", "-p", "--tools", "", "--no-session-persistence", "--effort", effort,
         "--model", model, "--system-prompt", system],
        input=prompt, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
    return out.stdout.strip()


def _json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- critique

def critique(points: list[dict], plan: str, decklist: str, model: str, effort: str = "high",
             workers: int = 4, prompts: list[str] | None = None, memos: list[str] | None = None,
             extra_info: list[str] | None = None) -> list[dict]:
    """Review memos. Defaults: the v2 prompt and logged memo per point, with our decklist and card text as the
    information the strategist lacked. For another strategist, pass its verbatim prompts, its memos, and
    whatever it still lacked (e.g. the opponents' actual lists)."""
    def run(k: int) -> dict:
        p = points[k]
        memo = memos[k] if memos else p["memo"]
        extra = extra_info[k] if extra_info else (
            "Our actual 100-card decklist, with the builder's role notes:\n" + decklist
            + "\n\nOracle text for cards in view (our hand, all battlefields, stack):\n"
            + json.dumps(p["state"].get("card_text", {}), ensure_ascii=False))
        prompt = (
            "=== WHAT THE STRATEGIST SAW (verbatim prompt) ===\n" + (prompts[k] if prompts else strategist_prompt(plan, p))
            + "\n\n=== THE MEMO IT WROTE ===\n" + memo
            + "\n\n=== EXTRA INFORMATION THE STRATEGIST DID NOT HAVE ===\n" + extra
            + "\n\nReview the memo.")
        reply = _claude(CRITIC_SYSTEM, prompt, model, effort)
        return {"game": p["game"], "turn": p["turn"], "stratum": p.get("stratum"), "reason": p["reason"],
                "memo": memo, "review": _json(reply), "raw": None if _json(reply) else reply[:2000]}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(run, range(len(points))))


def summarize_critique(results: list[dict]) -> dict:
    ok = [r for r in results if r["review"]]
    scores = defaultdict(list)
    for r in ok:
        for k, v in (r["review"].get("scores") or {}).items():
            if isinstance(v, (int, float)):
                scores[k].append(v)
    kinds, cats = Counter(), Counter()
    for r in ok:
        for s in r["review"].get("shortcomings") or []:
            kinds[s.get("type")] += 1
            if s.get("type") == "information":
                cats[s.get("info_category")] += 1
    by_stratum = defaultdict(list)
    for r in ok:
        sc = r["review"].get("scores") or {}
        vals = [v for v in sc.values() if isinstance(v, (int, float))]
        if vals:
            by_stratum[r["stratum"]].append(sum(vals) / len(vals))
    return {"reviewed": len(ok), "failed": len(results) - len(ok),
            "mean_scores": {k: round(sum(v) / len(v), 2) for k, v in scores.items()},
            "mean_by_stratum": {k: round(sum(v) / len(v), 2) for k, v in by_stratum.items()},
            "shortcoming_types": dict(kinds), "information_gaps": dict(cats.most_common())}


def critique_report(results: list[dict], summary: dict) -> str:
    L = [f"Reviewed {summary['reviewed']} memos ({summary['failed']} unparsed).",
         "Mean scores (0-3): " + ", ".join(f"{k} {v}" for k, v in summary["mean_scores"].items()),
         "By stratum (mean of dimensions): " + ", ".join(f"{k} {v}" for k, v in summary["mean_by_stratum"].items()),
         f"Shortcomings: {summary['shortcoming_types']}; information gaps by category: {summary['information_gaps']}",
         ""]
    for r in results:
        if not r["review"]:
            continue
        rv = r["review"]
        L.append(f"--- {r['game']} turn {r['turn']} ({r['stratum']}): {rv.get('scores')}")
        L.append(f"    biggest miss: {rv.get('biggest_miss', '')[:300]}")
        for s in (rv.get("shortcomings") or [])[:4]:
            tag = s.get("type", "?")
            extra = f" [needs: {s.get('missing_info')}]" if tag == "information" else ""
            L.append(f"    - {tag}: {str(s.get('what', ''))[:200]}{extra[:200]}")
    return "\n".join(L)


# --------------------------------------------------------------------------- A/B

def ab_compare(points: list[dict], memos_a: list[str], memos_b: list[str], model: str, effort: str = "high",
               workers: int = 4, seed: int = 7, extra_context: str = "") -> dict:
    """Blind pairwise judgment of two memo sets on the same boards. Returns tallies for 'a' and 'b'."""
    rng = random.Random(seed)
    order = [rng.random() < 0.5 for _ in points]

    def run(k: int) -> dict:
        p, a_first = points[k], order[k]
        first, second = (memos_a[k], memos_b[k]) if a_first else (memos_b[k], memos_a[k])
        prompt = (f"Board (JSON, with oracle text):\n{json.dumps(p['state'], ensure_ascii=False)}\n\n"
                  f"{extra_context}\n\nMemo A:\n{first}\n\nMemo B:\n{second}\n\nWhich memo is better?")
        reply = _claude(AB_SYSTEM, prompt, model, effort)
        m = re.match(r"\W*(A|B|SAME)\b", reply, re.I)
        verdict = "unparsed"
        if m:
            v = m.group(1).upper()
            verdict = "same" if v == "SAME" else ("a" if (v == "A") == a_first else "b")
        return {"game": p["game"], "turn": p["turn"], "verdict": verdict, "reply": reply[:400]}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run, range(len(points))))
    tally = Counter(r["verdict"] for r in results)
    from .pilot_audit import sign_test
    decided = tally["a"] + tally["b"]
    return {"tally": dict(tally), "b_share_of_decided": round(tally["b"] / decided, 3) if decided else None,
            "sign_test_p": round(sign_test(tally["b"], decided), 4), "results": results}
