"""Opus vs Haiku strategist: regenerate memos for the same logged boards, then judge blind.

Stages (each cached to disk so a crash or spend limit doesn't lose work):
  gen    memos per arm per point, using the production path: strategist.prompt + system_for(1),
         draft at the arm's effort, then the verify pass (low) by the same model.
  judge  blind pairwise, random order, judge sees the strategist's full prompt. Returns JSON
         with a verdict, per-memo errors with severity, and whether the difference would change play.
"""
import json, os, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import claude_cli, strategist, memo_lab
from edhkit.cards import CardDB
from edhkit.deck import Deck
from edhkit.pilot import deck_plan

S = Path(os.environ.get("EDH_RUNS", "."))  # folder holding the vivi-opus10{j,l,m} sim outputs
OUT = Path(os.environ.get("EDH_AB_OUT", "research/2026-10-08-strategist-model-ab-data"))
DECK = Path(__file__).resolve().parent.parent / "decks/vivi-ornitier/edhrec-b3"
ARMS = {"opus": ("claude-opus-5-5", "medium"), "haiku": ("claude-haiku-5-5", "medium"),
        "haiku_high": ("claude-haiku-5-5", "high")}

JUDGE_SYSTEM = (
    "You are a world-class Commander (EDH) player. Two strategy memos, A and B, were written for the same board "
    "by different strategists who saw exactly the prompt shown. A fast executor model follows the memo for every "
    "decision this turn. Judge which memo leads to better play from this exact position: threat assessment, how "
    "answers are budgeted, the target board state, the win path, risk, and concrete sequencing this turn. "
    "Check every claim against the prompt: mana arithmetic, card text, legality, targets, life totals. Longer is "
    "not better in itself; the executor must be able to follow the memo.\n\n"
    "Reply with only a JSON object:\n"
    '{"errors_A": [{"what": "...", "severity": "minor" | "major"}], "errors_B": [...], '
    '"verdict": "A" | "B" | "SAME", "margin": "slight" | "clear" | "decisive" | null, '
    '"play_differs": true | false, "reason": "<= 50 words"}\n'
    "A major error is one that, if followed, loses a card, mana, tempo or the game, or is an illegal or "
    "impossible play. play_differs: would an executor following A and one following B make a materially "
    "different play this turn cycle?")


def points(n=36):
    pts = []
    for r in "jlm":
        for p in memo_lab.load_memo_points(S / f"vivi-opus10{r}" / "pilot_decisions.jsonl"):
            p["run"] = r
            p["game"] = f"{r}:{p['game']}"
            pts.append(p)
    return memo_lab.sample_points(pts, n, seed=5)


def gen(pts, deck, db, plan):
    cache = OUT / "memos.json"
    memos = json.loads(cache.read_text()) if cache.exists() else {}
    system = strategist.system_for(1)

    def one(job):
        k, arm = job
        key = f"{k}:{arm}"
        if key in memos and memos[key].get("memo"):
            return
        model, effort = ARMS[arm]
        p = pts[k]
        prompt = strategist.prompt(plan, deck, db, p["state"], p["previous_memo"], p["reason"])
        t0 = time.time()
        try:
            draft = claude_cli.run(system, prompt, model, effort, timeout=600)
            t1 = time.time()
            memo = claude_cli.run(strategist.verify_system(1), strategist.verify_prompt(prompt, draft), model, "low",
                                  timeout=600)
            memos[key] = {"memo": memo[:3000], "draft": draft, "draft_s": round(t1 - t0, 1),
                          "verify_s": round(time.time() - t1, 1)}
        except claude_cli.ClaudeCallFailed as e:
            memos[key] = {"memo": "", "error": str(e)}
            print("FAIL", key, e, flush=True)
        cache.write_text(json.dumps(memos, indent=1))
        print("gen", key, memos[key].get("draft_s"), memos[key].get("verify_s"), flush=True)

    jobs = [(k, a) for k in range(len(pts)) for a in ARMS]
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one, jobs))
    return memos


def judge(pts, memos, deck, db, plan, base, other, judge_model, effort="high"):
    cache = OUT / f"judge_{base}_vs_{other}_{judge_model}.json"
    res = json.loads(cache.read_text()) if cache.exists() else {}
    rng = random.Random(11)
    order = [rng.random() < 0.5 for _ in pts]

    def one(k):
        if str(k) in res and res[str(k)].get("verdict") in ("base", "other", "same"):
            return
        ma, mb = memos.get(f"{k}:{base}", {}).get("memo"), memos.get(f"{k}:{other}", {}).get("memo")
        if not ma or not mb:
            return
        p = pts[k]
        base_first = order[k]
        A, B = (ma, mb) if base_first else (mb, ma)
        prompt = (f"=== THE STRATEGISTS' PROMPT ===\n{strategist.prompt(plan, deck, db, p['state'], p['previous_memo'], p['reason'])}"
                  f"\n\n=== MEMO A ===\n{A}\n\n=== MEMO B ===\n{B}\n\nJudge.")
        try:
            reply = claude_cli.run(JUDGE_SYSTEM, prompt, judge_model, effort, timeout=900)
        except claude_cli.ClaudeCallFailed as e:
            print("judge FAIL", k, e, flush=True)
            return
        j = memo_lab._json(reply) or {}
        v = str(j.get("verdict", "")).upper()
        verdict = "same" if v == "SAME" else ("base" if (v == "A") == base_first else "other") if v in "AB" and v else "unparsed"
        eb, eo = (j.get("errors_A"), j.get("errors_B")) if base_first else (j.get("errors_B"), j.get("errors_A"))
        res[str(k)] = {"verdict": verdict, "margin": j.get("margin"), "play_differs": j.get("play_differs"),
                       "errors_base": eb or [], "errors_other": eo or [], "reason": j.get("reason"),
                       "stratum": p.get("stratum"), "game": p["game"], "turn": p["turn"]}
        cache.write_text(json.dumps(res, indent=1))
        print("judge", k, verdict, j.get("margin"), flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(one, range(len(pts))))
    return res


if __name__ == "__main__":
    stage = sys.argv[1]
    pts = points(int(sys.argv[2]) if len(sys.argv) > 2 else 36)
    deck, db = Deck.load(DECK / "deck.txt"), CardDB()
    plan = deck_plan(DECK / "brief.md", DECK / "notes.md")
    (OUT / "points.json").write_text(json.dumps([{k: p[k] for k in ("game", "turn", "reason", "stratum")} for p in pts], indent=1))
    if stage == "gen":
        gen(pts, deck, db, plan)
    elif stage == "judge":
        memos = json.loads((OUT / "memos.json").read_text())
        base, other, jm = sys.argv[3], sys.argv[4], sys.argv[5]
        judge(pts, memos, deck, db, plan, base, other, jm)
    elif stage == "prompt":
        p = pts[0]
        print(strategist.prompt(plan, deck, db, p["state"], p["previous_memo"], p["reason"]))
