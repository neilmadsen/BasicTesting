"""One turn up close: the board, the strategist's memo, and every decision the pilot made against it.

    python3 research/turn_view.py <sim-out> <game> <turn> [--deck deck.txt]

Reads the pilot log only (needs --log-state), so it works while a run is still going. For each decision it shows
Forge's own choice, Jev's, both probabilities, and the plan tag on Jev's pick, then the board at the next logged
decision so the turn's result is visible.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit import pilot as P  # noqa: E402
from edhkit.deck import Deck  # noqa: E402
from edhkit.scorecard import _log, _open  # noqa: E402


def _board(state: dict) -> list[str]:
    out = []
    for p in state.get("players", []):
        nonland = [x for x in p.get("battlefield", []) if "[land]" not in x]
        lands = sum(P.parse_entry(x)["n"] for x in p.get("battlefield", []) if "[land]" in x)
        who = "US" if p.get("is_me") else p["name"]
        out.append(f"  {who} ({', '.join(p.get('commanders', []))[:30]}): {p.get('life')} life, {lands} lands, "
                   f"hand {p.get('hand_size')}; {', '.join(nonland) or 'no nonland permanents'}")
    return out


def view(sim: Path, game: str, turn: int, deck: Path | None) -> str:
    if deck:
        P.set_deck_names(Deck.load(deck).names())
    recs = [json.loads(line) for line in _open(_log(sim))]
    mine = [r for r in recs if r.get("game") == game]
    memo = next((r for r in mine if r.get("type") == "memo" and r["turn"] == turn), None)
    decs = [r for r in mine if r.get("type") == "decision" and r.get("turn") == turn]
    if not decs:
        return f"no decisions logged for {game} turn {turn}"
    st = decs[0]["state"]
    lines = [f"=== {game}, turn {turn} (board at our first decision)",
             f"  our mana {st.get('my_mana_available')}; hand: {', '.join(st.get('my_hand', []))}"] + _board(st)
    lines.append("  recent casts: " + "; ".join(st.get("recent_casts", [])[-8:]))
    if memo:
        lines += ["", f"--- memo ({memo.get('reason', '')}, {round((memo.get('ms') or 0) / 1000)} s)", memo["memo"].strip()]
    lines += ["", "--- decisions"]
    for d in decs:
        tags = P.option_tags({"kind": d["kind"], "state": d["state"], "questions": d["questions"]},
                             d.get("memo") or "", d.get("memo_age") or 0)
        for a in d["answers"]:
            if a.get("unused"):
                continue
            q = next(q for q in d["questions"] if q["id"] == a["q"])
            opts = {o["id"]: o["text"] for o in q["options"]}
            if d["kind"] == "action" and a["q"].startswith(("tgt_", "x_")):
                continue
            head = q["prompt"][:60] if d["kind"] not in ("action",) else ("hold?" if a["q"] == "hold" else "play?")
            same = a["choice"] == a["default"]
            lines.append(f"  [{d.get('phase')}, mana {d['state'].get('my_mana_available')}] {d['kind']} {head}")
            lines.append(f"      Jev: {opts.get(a['choice'], a['choice'])[:110]}  (p {a.get('p')})"
                         + ("  = Forge" if same else f"\n      Forge wanted: {opts.get(a['default'], a['default'])[:90]}"
                                                     f"  (p {a.get('p_default')})") + ("  [gated back to Forge]" if a.get("gated") else ""))
            tag = tags.get(a["q"], {}).get(a["choice"], "")
            if tag:
                lines.append(f"      tag: {tag.strip()[:200]}")
    later = [r for r in mine if r.get("type") == "decision" and r.get("turn", 0) > turn]
    if later:
        lines += ["", f"--- board at the next logged decision (turn {later[0]['turn']}, {later[0].get('phase')})"]
        lines += _board(later[0]["state"])
        lines.append("  recent casts: " + "; ".join(later[0]["state"].get("recent_casts", [])[-8:]))
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sim")
    ap.add_argument("game")
    ap.add_argument("turn", type=int)
    ap.add_argument("--deck")
    a = ap.parse_args()
    print(view(Path(a.sim), a.game, a.turn, Path(a.deck) if a.deck else None))
