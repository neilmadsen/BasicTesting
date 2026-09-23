"""Functional role tags from Scryfall Tagger (the community-maintained `otag:` data).

Scryfall doesn't ship tags in bulk files, so we harvest the ones that matter for
deck composition with paginated searches (one-time, ~2 minutes, re-run monthly).
Tags are deliberately coarse; they answer "what job does this card do", not
"is it good". Taste is the agent's job; this is bookkeeping.
"""

from __future__ import annotations

import sys
import time
import urllib.parse

from . import net
from .cards import CardDB

# tag -> short description (shown by `edh tags list`)
TAGS: dict[str, str] = {
    # mana
    "ramp": "any mana acceleration",
    "mana-rock": "artifact that taps for mana",
    "mana-dork": "creature that taps for mana",
    "land-ramp": "puts extra lands onto the battlefield",
    "extra-land": "lets you play additional lands",
    "cost-reducer": "makes spells cheaper",
    "untapper": "untaps permanents",
    # cards
    "draw": "draws cards (including cantrips)",
    "repeatable-draw": "draw engine: draws more than once",
    "card-advantage": "net card advantage of any kind",
    "impulsive-draw": "exile-and-play card advantage",
    "cantrip": "replaces itself",
    "wheel": "everyone discards/shuffles and draws a new hand",
    "tutor": "searches library for a card",
    # interaction
    "removal": "removes permanents (broad)",
    "spot-removal": "targeted removal",
    "creature-removal": "removes creatures",
    "artifact-removal": "removes artifacts",
    "enchantment-removal": "removes enchantments",
    "board-wipe": "mass removal",
    "counterspell": "counters spells",
    "bounce": "returns permanents to hand",
    "theft": "gains control of opponents' stuff",
    "burn": "direct damage",
    "discard": "makes opponents discard",
    "graveyard-hate": "exiles or neuters graveyards",
    "hatebear": "creature with a taxing/stax static ability",
    "tax": "taxes opponents' actions",
    "mass-land-denial": "mass land denial (bracket-restricted)",
    "fog": "prevents combat damage",
    "pillowfort": "discourages attacks against you",
    # resilience
    "protection": "protects your permanents",
    "gives-hexproof": "grants hexproof/shroud",
    "gives-indestructible": "grants indestructible",
    "recursion": "returns cards from graveyard",
    "reanimate": "returns creatures from graveyard to battlefield",
    # engines / themes
    "sacrifice-outlet": "lets you sacrifice permanents",
    "death-trigger": "triggers when creatures die",
    "self-mill": "mills yourself",
    "discard-outlet": "lets you discard cards",
    "lifegain": "gains life",
    "mill": "mills opponents",
    "anthem": "pumps your team",
    "blink": "flickers permanents",
    "copy": "copies spells or permanents",
    "clone": "creature that copies a creature",
    "combat-trick": "instant-speed combat pump/trick",
    "mana-sink": "repeatable use for excess mana",
    # win / bracket-relevant
    "extra-turn": "takes extra turns (bracket-restricted)",
    "win-condition": "wins the game outright / alt-win",
}


def harvest(tags: list[str] | None = None, verbose: bool = True) -> dict[str, int]:
    db = CardDB()
    con = db.con
    tags = tags or list(TAGS)
    counts: dict[str, int] = {}
    known = {r[0] for r in con.execute("SELECT oracle_id FROM cards")}
    for tag in tags:
        q = urllib.parse.quote(f"otag:{tag} f:commander")
        url = f"https://api.scryfall.com/cards/search?q={q}&unique=cards&order=name"
        found: list[str] = []
        while url:
            try:
                page = net.get_json(url)
            except RuntimeError as e:
                if "404" in str(e):  # tag doesn't exist / no cards
                    break
                raise
            found += [c["oracle_id"] for c in page.get("data", []) if c.get("oracle_id") in known]
            url = page.get("next_page") if page.get("has_more") else None
        con.execute("DELETE FROM card_tags WHERE tag=?", (tag,))
        con.executemany("INSERT OR IGNORE INTO card_tags VALUES (?,?)", [(o, tag) for o in found])
        con.commit()
        counts[tag] = len(found)
        if verbose:
            print(f"  {tag:22s} {len(found):5d}", file=sys.stderr)
    con.execute("INSERT OR REPLACE INTO meta VALUES ('tags_harvested_at', ?)", (time.strftime("%Y-%m-%d"),))
    con.commit()
    return counts


def tag_counts() -> dict[str, int]:
    db = CardDB()
    return dict(db.con.execute("SELECT tag, count(*) FROM card_tags GROUP BY tag ORDER BY tag").fetchall())
