"""Regenerate the strategist's memo at one logged decision point, under the current prompt and pilot code.

    python3 research/memo_probe.py <sim-out> <game> <turn> --deck deck.txt [--reason "..."] [--effort medium]

Uses the first logged decision of that turn as the board, the memo in force at that point as the previous memo,
and (by default) the reason the current pilot would give: an early re-plan when plan-breaking changes happened
since the previous round, else a scheduled plan. A strategist fix can be checked against the exact boards where
the old one failed, one model call each, before any new games.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import claude_cli, strategist  # noqa: E402
from edhkit.cards import CardDB  # noqa: E402
from edhkit.deck import Deck  # noqa: E402
from edhkit.pilot import STRATEGIST_MODEL, changes_since, deck_plan, new_danger, plan_breaking  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("sim"); ap.add_argument("game"); ap.add_argument("turn", type=int)
ap.add_argument("--deck", required=True); ap.add_argument("--reason"); ap.add_argument("--effort", default="medium")
ap.add_argument("--verify", default="low"); ap.add_argument("--show-prompt", action="store_true")
a = ap.parse_args()
memo, state, prev_round = "", None, None
for line in (Path(a.sim) / "pilot_decisions.jsonl").open():
    r = json.loads(line)
    if r.get("game") != a.game:
        continue
    t = r.get("turn") or 0
    if t >= a.turn and r.get("type") == "decision" and "state" in r:
        state = r["state"]; break
    if r.get("type") == "memo":
        memo = r["memo"]
    if r.get("type") == "decision" and "state" in r and r["state"].get("active") == r["state"].get("me"):
        if prev_round is None or r["state"].get("turn") != prev_round.get("turn"):
            prev_round = r["state"]
if state is None:
    sys.exit("no decision at or after that turn")
shocks = plan_breaking(changes_since(prev_round, state) + new_danger(prev_round, state)) if prev_round else []
reason = a.reason or ("start of our turn, re-planning early because the board changed: " + "; ".join(shocks)
                      if shocks else "start of our turn")
folder = Path(a.deck).resolve().parent
plan = deck_plan(folder / "brief.md", folder / "notes.md")
prompt = strategist.prompt(plan, Deck.load(a.deck), CardDB(), state, memo, reason)
if a.show_prompt:
    print(prompt); sys.exit()
draft = claude_cli.run(strategist.system_for(1), prompt, STRATEGIST_MODEL, a.effort, timeout=600)
final = claude_cli.run(strategist.verify_system(1), strategist.verify_prompt(prompt, draft), STRATEGIST_MODEL,
                       a.verify, timeout=600) if a.verify != "off" else draft
print(f"REASON: {reason}\nHAND: {state.get('my_hand')}\n\n{final}")
