"""Read the card pool like a deckbuilder: every legal card matching a pattern, full text, in pages.

`jev rank` and `scry` find cards you can describe. Browsing finds the ones you can't: the builder asks for
"every card in Obeka's identity that mentions upkeep", gets a count by type first, then reads the whole
slice page by page with the complete oracle text and how often this commander's decks already run each
card. Reading 900 cards in ten pages is how a human expert would scout a niche mechanic, and it is cheap.
"""
from __future__ import annotations

import re
from collections import Counter

from .cards import Card, CardDB
from .search import Filters, pool

GROUPS = ("Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Land")


def group_of(c: Card) -> str:
    """Primary type for grouping. Artifact creatures count as creatures, enchantment lands as lands."""
    tl = c.type_line.split("//")[0]
    for g in GROUPS:
        if g in tl:
            return g
    return "Other"


def inclusion_map(commanders: list[str], bracket: int | None = None) -> tuple[dict[str, float], int]:
    """Card name -> share of this commander's EDHREC decks running it, plus the deck count. Empty offline.
    EDHREC lists roughly the top 600 cards per commander, so an absent card is below that list's floor."""
    from . import edhrec
    try:
        page = edhrec.commander_page(commanders, bracket)
    except Exception:  # noqa: BLE001 - offline or blocked; browsing still works without it
        return {}, 0
    out = {n: v["inclusion"] for n, v in page.get("cards", {}).items() if v.get("inclusion") is not None}
    return out, int(page.get("num_decks") or 0)


def select(db: CardDB, f: Filters, not_regex: str | None = None) -> list[Card]:
    f.limit = None
    cards = pool(db, f)
    if not_regex:
        rx = re.compile(not_regex, re.I)
        cards = [c for c in cards if not rx.search(c.text or "")]
    return cards


def order(cards: list[Card], group: str, sort: str) -> list[Card]:
    def key(c: Card):
        base = {"mv": (c.cmc, c.name), "name": (c.name,), "edhrec": (c.edhrec_rank or 10**6, c.name),
                "newest": (-(int((c.released_at or "0").replace("-", "") or 0)), c.name)}[sort]
        if group == "type":
            return (GROUPS.index(group_of(c)) if group_of(c) in GROUPS else 99, *base)
        if group == "mv":
            return (min(int(c.cmc), 7), *base)
        return base
    return sorted(cards, key=key)


def card_block(c: Card, incl: dict[str, float], have_incl: bool, deck_names: set[str]) -> str:
    pt = f" {c.pt}" if c.pt else ""
    flags = []
    if c.game_changer:
        flags.append("GC")
    if c.name in deck_names:
        flags.append("IN DECK")
    if have_incl:
        share = incl.get(c.name)
        flags.append(f"{share:.0%} of decks" if share is not None else "unlisted")
    if c.edhrec_rank:
        flags.append(f"rank #{c.edhrec_rank}")
    text = (c.text or "").replace("\n", " / ")
    return f"- **{c.name}** {c.mana_cost or ''} · {c.type_line}{pt} · {' · '.join(flags)}\n  {text}"


def browse(cards: list[Card], *, page: int = 1, per_page: int = 80, group: str = "type", sort: str = "mv",
           incl: dict[str, float] | None = None, num_decks: int = 0, deck_names: set[str] | None = None,
           title: str = "") -> str:
    incl = incl or {}
    deck_names = deck_names or set()
    cards = order(cards, group, sort)
    pages = max(1, -(-len(cards) // per_page))
    page = min(max(1, page), pages)
    chunk = cards[(page - 1) * per_page: page * per_page]
    by_type = Counter(group_of(c) for c in cards)
    L = [f"# {title or 'Card pool'}",
         f"{len(cards)} cards · page {page}/{pages} ({per_page} per page) · "
         + ", ".join(f"{g} {n}" for g, n in sorted(by_type.items(), key=lambda t: -t[1]))]
    if incl:
        listed = sum(1 for c in cards if c.name in incl)
        L.append(f"EDHREC: {num_decks} decks for this commander; {listed} of these cards appear in its list, "
                 f"{len(cards) - listed} unlisted (rarely or never played with it).")
    current = None
    for c in chunk:
        head = group_of(c) if group == "type" else (f"MV {min(int(c.cmc), 7)}{'+' if c.cmc >= 7 else ''}"
                                                  if group == "mv" else None)
        if head and head != current:
            L.append(f"\n## {head}")
            current = head
        L.append(card_block(c, incl, bool(incl), deck_names))
    if page < pages:
        L.append(f"\n(next: --page {page + 1})")
    return "\n".join(L)
