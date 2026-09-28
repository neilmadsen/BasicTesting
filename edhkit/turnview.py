"""One turn up close: the board, the strategist's memo, and every decision the pilot made against it (all options,
with J = Jev's final answer and F = Forge's own pick).

    python3 research/turn_view.py <sim-out> <game> <turn> [--deck deck.txt]
    (also used by the turn auditor, edhkit/turn_audit.py)

Reads the pilot log only (needs --log-state), so it works while a run is still going. For each decision it shows
Forge's own choice, Jev's, both probabilities, and the plan tag on Jev's pick, then the board at the next logged
decision so the turn's result is visible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import pilot as P
from .deck import Deck
from .scorecard import _log, _open


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
    lines += ["", "--- decisions (every option on offer, its memo tags, Forge's pick and Jev's)"]
    for d in decs:
        tags = P.option_tags({"kind": d["kind"], "state": d["state"], "questions": d["questions"],
                              **(d.get("context") or {})}, d.get("memo") or "", d.get("memo_age") or 0)
        ctx = d.get("context") or {}
        lines.append(f"  [{d.get('phase')}, mana {d['state'].get('my_mana_available')}] {d['kind']}"
                     + (f" — window: {ctx['window']}" if ctx.get("window") else "")
                     + (f" — {ctx['incoming']}" if ctx.get("incoming") else "")
                     + (f" — SCAN CUT: {ctx['scan_truncated']}" if ctx.get("scan_truncated") else ""))
        for a in d["answers"]:
            if a.get("unused"):
                continue
            q = next(q for q in d["questions"] if q["id"] == a["q"])
            opts = {o["id"]: o["text"] for o in q["options"]}
            head = q["prompt"][:90]
            lines.append(f"    Q {a['q']}: {head}")
            for oid, text in opts.items():
                mark = ("J" if oid == a["choice"] else " ") + ("F" if oid == a["default"] else " ")
                lines.append(f"      {mark} {oid}: {text[:110]}{tags.get(a['q'], {}).get(oid, '')[:150]}")
            if a.get("gated"):
                raw = a.get("raw_choice")
                lines.append(f"      (Jev's own pick {raw or a['choice']!s} was GATED back to Forge's; margin {a.get('margin')})")
            lines.append(f"      p(Jev pick) {a.get('p')}, p(Forge pick) {a.get('p_default', a.get('p'))}")
    later = [r for r in mine if r.get("type") == "decision" and r.get("turn", 0) > turn]
    if later:
        lines += ["", f"--- board at the next logged decision (turn {later[0]['turn']}, {later[0].get('phase')})"]
        lines += _board(later[0]["state"])
        lines.append("  recent casts: " + "; ".join(later[0]["state"].get("recent_casts", [])[-8:]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sim")
    ap.add_argument("game")
    ap.add_argument("turn", type=int)
    ap.add_argument("--deck")
    a = ap.parse_args()
    print(view(Path(a.sim), a.game, a.turn, Path(a.deck) if a.deck else None))


if __name__ == "__main__":
    main()
