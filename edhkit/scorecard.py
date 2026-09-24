"""Execution scorecard for a piloted sim: how well our seat was played, from the logs, with no model calls.

    ./edh scorecard <sim-out> [<sim-out> ...]

Win rate over a few dozen games is too noisy to steer executor work; these counts aren't. Each metric is a
mistake class found in the v3.1 post-mortem (research/2026-09-24-postmortem.md), counted per game, so two runs
(or two executor versions on the same pods) can be compared directly. Needs a --log-state pilot log for the
option-level metrics; the rest work on any pilot log.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

_OUTLOOK = re.compile(r"(\d+) would kill it and survive, (\d+) would trade")
_LANDS = re.compile(r"Opening hand of (\d+) cards: (\d+) lands?")
_CARD = re.compile(r"^(?:cast|activate|play land) (.+?) \(from ")


def _open(p: Path):
    return gzip.open(p, "rt") if p.suffix == ".gz" else p.open()


def _log(sim: Path) -> Path:
    for name in ("pilot_decisions.jsonl", "pilot_decisions.jsonl.gz"):
        if (sim / name).exists():
            return sim / name
    raise FileNotFoundError(f"no pilot_decisions.jsonl in {sim}")


def _land_lookup():
    """name -> is it a land card (card DB; without one, nothing counts as a land)."""
    try:
        from .cards import CardDB
        db = CardDB()
    except BaseException:  # CardDB raises SystemExit when the DB is missing
        return lambda name: False

    def is_land(name: str) -> bool:
        card = db.get(name)
        return bool(card and card.is_land)
    return is_land


def score(sim: Path, is_land=None) -> dict:
    """Per-run counts. is_land: name -> bool, to classify sacrificed permanents (default: the card DB)."""
    is_land = is_land or _land_lookup()
    games, c = set(), Counter()
    planned_names = defaultdict(set)   # (game, turn) -> planned card names offered this turn
    played_names = defaultdict(set)    # (game, turn) -> card names we chose
    last_main2 = {}                    # (game, turn) -> the last main-2 action record
    for line in _open(_log(sim)):
        d = json.loads(line)
        g = d.get("game")
        if g:
            games.add(g)
        t = d.get("type")
        if t == "memo":
            c["memos"] += 1
            c["memos: escalation"] += d.get("reason", "").startswith("executor escalation")
            continue
        if t == "memo_error":
            c["memo errors"] += 1
            continue
        if t != "decision":
            continue
        kind, key = d["kind"], (g, d.get("turn"))
        qs = {q["id"]: q for q in d.get("questions", [])}
        for a in d["answers"]:
            if a.get("unused"):
                continue
            q = qs.get(a["q"])
            opts = {o["id"]: o["text"] for o in q["options"]} if q else {}
            chosen = opts.get(a["choice"], a.get("label", ""))
            c[f"questions: {kind}"] += 1
            c[f"overrules: {kind}"] += a["choice"] != a["default"]
            c[f"gated: {kind}"] += bool(a.get("gated"))
            if kind == "action" and a["q"] == "action":
                marked = a.get("plan_marked") or []
                held = a.get("hold_marked") or []
                if held:
                    c["hold: windows offering a card the memo holds"] += 1
                    c["hold: held card played"] += a["choice"] in held and a["choice"] not in marked
                age = "fresh memo" if not d.get("memo_age") else "older memo"
                if marked:
                    c[f"plan: windows with a planned play ({age})"] += 1
                    c[f"plan: planned play taken ({age})"] += a["choice"] in marked
                    for oid in marked:
                        m = _CARD.match(opts.get(oid, ""))
                        if m:
                            planned_names[key].add(m.group(1))
                m = _CARD.match(chosen)
                if m:
                    played_names[key].add(m.group(1))
                window = d.get("context", {}).get("window", "")
                if d.get("phase") == "MAIN2" and window.startswith("our main"):
                    last_main2[key] = (a, opts, d.get("state", {}))
            elif kind == "attack" and a["choice"] != "hold":
                mo = _OUTLOOK.search(chosen)
                if mo and (int(mo.group(1)) or int(mo.group(2))):
                    c["combat: attacks where a blocker can kill it"] += 1
                    c["combat: ... of them overruling Forge's hold"] += a["default"] == "hold"
                    c["combat: ... of them our commander"] += "commander" in (q["prompt"] if q else "")
            elif kind == "block" and a["choice"] != "none":
                c["combat: blocks where ours dies without killing"] += "doesn't kill it, ours dies" in chosen
            elif kind == "mulligan":
                mo = _LANDS.search(q["prompt"] if q else "")
                if mo and a["choice"] == "keep":
                    n, lands = int(mo.group(1)), int(mo.group(2))
                    c["mulligan: kept"] += 1
                    c["mulligan: kept with <=1 land"] += lands <= 1
                    c["mulligan: kept 7 with >=6 lands"] += n == 7 and lands >= 6
            elif kind in ("sacrifice-cost", "sacrifice"):
                if a["choice"] == "none":
                    c[f"{kind}: cancelled" if kind == "sacrifice-cost" else "sacrifice: declined"] += 1
                else:
                    c[f"{kind}: paid"] += 1
                    c[f"{kind}: a land"] += is_land(chosen.split(" [")[0])
            elif kind in ("trigger-target",) or a["q"].startswith("tgt_"):
                if a["choice"] != a["default"] and "[ours" in chosen and "[ours" not in opts.get(a["default"], "[ours"):
                    c["targets: overruled Forge to aim at our own card"] += 1
            elif kind == "confirm" and q and re.search(r": Pay \d+ life\?", q["prompt"]):
                c["pay life for untapped land: asked"] += 1
                c["pay life for untapped land: paid"] += a["choice"] == "yes"
            if a["q"].startswith("x_"):
                c["X: asked"] += 1
                c["X: left to Forge"] += a["choice"] == "auto"
    for key, (a, opts, state) in last_main2.items():
        plays = [v for k, v in opts.items() if not v.startswith(("Take no further", "play land"))]
        if a["choice"] == "pass" and plays and state.get("my_mana_available", 0) >= 3:
            c["mana: turns ended with 3+ mana and a castable play"] += 1
    for key, names in planned_names.items():
        c["plan: planned cards offered but not played that turn"] += len(names - played_names.get(key, set()))
    n = max(1, len(games))
    out = {"games": len(games), "per_game": {k: round(v / n, 2) for k, v in sorted(c.items())}, "totals": dict(c)}
    for age in ("fresh memo", "older memo"):
        w = c[f"plan: windows with a planned play ({age})"]
        if w:
            out[f"plan_taken_share ({age})"] = round(c[f"plan: planned play taken ({age})"] / w, 3)
    summary = sim / "summary.json"
    if summary.exists():
        s = json.loads(summary.read_text())
        out["result"] = {k: s.get(k) for k in ("games", "wins", "win_rate", "avg_round_we_died",
                                                "commander_cast_rate", "commander_avg_first_round")}
    return out


def report(scores: dict[str, dict]) -> str:
    """Side-by-side per-game metrics for one or more runs."""
    names = list(scores)
    keys = sorted({k for s in scores.values() for k in s["per_game"]})
    width = max(len(k) for k in keys) if keys else 20
    lines = ["per game".ljust(width) + "".join(f"  {n[-18:]:>18}" for n in names)]
    lines.append("games".ljust(width) + "".join(f"  {scores[n]['games']:>18}" for n in names))
    for k in keys:
        lines.append(k.ljust(width) + "".join(f"  {scores[n]['per_game'].get(k, 0):>18}" for n in names))
    for k in ("plan_taken_share (fresh memo)", "plan_taken_share (older memo)"):
        if any(k in s for s in scores.values()):
            lines.append(k.ljust(width) + "".join(f"  {str(scores[n].get(k, '-')):>18}" for n in names))
    for n in names:
        r = scores[n].get("result")
        if r:
            lines.append(f"{n}: won {r['wins']}/{r['games']}, commander cast {r['commander_cast_rate']} "
                         f"(first round {r['commander_avg_first_round']}), died round {r['avg_round_we_died']}")
    return "\n".join(lines)
