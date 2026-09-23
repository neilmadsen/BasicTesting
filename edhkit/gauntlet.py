"""Opponent pools for simulation, built from EDHREC average decks per bracket.

An "average deck" is a statistical composite of many real lists for one
commander at one bracket, so it's a fair stand-in for "a typical deck at this
power level". For each bracket we prefer commanders with many decks registered
*at that bracket* (so the average is meaningful), spread color identities, skip
decks Forge can't mostly play, and write Forge-ready files to gauntlet/b<N>/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import edhrec, forge
from .cards import CardDB
from .paths import GAUNTLET

# Popularity lists skew casual; seed bracket 5 with established cEDH commanders.
CEDH_SEEDS: list[list[str]] = [
    ["Kinnan, Bonder Prodigy"], ["Najeela, the Blade-Blossom"], ["Tivit, Seller of Secrets"],
    ["Urza, Lord High Artificer"], ["Magda, Brazen Outlaw"], ["Sisay, Weatherlight Captain"],
    ["Yuriko, the Tiger's Shadow"], ["Winota, Joiner of Forces"], ["Talion, the Kindly Lord"],
    ["Etali, Primal Conqueror"], ["Glarb, Calamity's Augur"], ["Godo, Bandit Warlord"],
    ["Kraum, Ludevic's Opus", "Tymna the Weaver"], ["Thrasios, Triton Hero", "Tymna the Weaver"],
    ["Rograkh, Son of Rohgahh", "Silas Renn, Seeker Adept"], ["Malcolm, Keen-Eyed Navigator", "Kediss, Emberclaw Familiar"],
]
MIN_DECKS_AT_BRACKET = {1: 8, 2: 40, 3: 40, 4: 40, 5: 15}


def _candidates(bracket: int, db: CardDB, n_top: int) -> list[tuple[list[str], int]]:
    pool: list[list[str]] = [[name] for name, _ in edhrec.top_commanders("year", limit=n_top)]
    if bracket == 5:
        pool = CEDH_SEEDS + pool
    scored = []
    seen = set()
    for names in pool:
        key = tuple(sorted(names))
        if key in seen or not all(db.get(n) for n in names):
            continue
        seen.add(key)
        try:
            page = edhrec.commander_page(names)
        except Exception:
            continue
        counts = page.get("bracket_counts") or {}
        n_at = int(counts.get(str(bracket), 0) or 0)
        if n_at >= MIN_DECKS_AT_BRACKET[bracket]:
            scored.append((names, n_at))
    scored.sort(key=lambda x: -x[1])
    return scored


def build(bracket: int, count: int = 12, db: CardDB | None = None, candidates: int = 100,
          max_unsupported: int = 3, verbose: bool = True) -> list[Path]:
    db = db or CardDB()
    outdir = GAUNTLET / f"b{bracket}"
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.dck"):
        old.unlink()
    idx = forge.build_card_index()
    ranked = _candidates(bracket, db, candidates)
    if verbose:
        print(f"  {len(ranked)} commanders with ≥{MIN_DECKS_AT_BRACKET[bracket]} decks at bracket {bracket}", file=sys.stderr)
    ci_used: dict[str, int] = {}
    written: list[Path] = []
    meta = []
    deferred: list[tuple[list[str], int]] = []
    for pass_no in (1, 2):
        source = ranked if pass_no == 1 else deferred
        for names, n_at in source:
            if len(written) >= count:
                break
            ci = "".join(sorted(set("".join(db.get(n).color_identity for n in names)) - {"C"})) or "C"
            if pass_no == 1 and ci_used.get(ci, 0) >= 1:
                deferred.append((names, n_at))  # spread identities first, then fill
                continue
            try:
                deck = edhrec.average_deck(names, bracket)
            except Exception:
                continue
            errs = deck.resolve(db)
            if deck.size() < 95 or len(errs) > 2:
                continue
            sup = forge.support_report(deck, idx)
            if len(sup["missing"]) > max_unsupported or any(e.name in sup["missing"] for e in deck.commanders):
                if verbose:
                    print(f"  skip {' + '.join(names)}: {len(sup['missing'])} cards not in Forge", file=sys.stderr)
                continue
            label = " + ".join(names)
            path = outdir / f"{edhrec.commander_slug(names)}.dck"
            path.write_text(deck.to_forge(label))
            written.append(path)
            ci_used[ci] = ci_used.get(ci, 0) + 1
            meta.append({"commander": label, "color_identity": ci, "file": path.name,
                         "decks_at_bracket": n_at, "forge_missing": sup["missing"],
                         "ai_cannot_play": sup["ai_cannot_play"]})
            if verbose:
                print(f"  + {label} [{ci}] ({n_at} decks at B{bracket})", file=sys.stderr)
    (outdir / "index.json").write_text(json.dumps(meta, indent=2))
    return written
