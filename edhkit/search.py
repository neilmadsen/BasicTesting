"""Candidate pools: local SQL/FTS filtering, and Scryfall-syntax passthrough.

Three ways to find cards, from precise to fuzzy:
  1. `scryfall(query)` — the full Scryfall syntax (o:, t:, otag:, mv<=, etc.),
     executed by Scryfall's API and mapped back onto the local DB.
  2. `pool(Filters)` — offline SQL filters + FTS5 keyword search.
  3. `edh.jev` — semantic judgement over whatever pool 1 or 2 produced.
"""

from __future__ import annotations

import random
import re
import urllib.parse
from dataclasses import dataclass, field

from . import net
from .cards import Card, CardDB, parse_colors


@dataclass
class Filters:
    ci_mask: int | None = None          # color identity must be a subset of this
    legal_only: bool = True
    types: list[str] = field(default_factory=list)       # all must appear in type_line
    not_types: list[str] = field(default_factory=list)
    text: str | None = None             # FTS5 MATCH expression over name/type/text
    regex: str | None = None            # Python regex over oracle text (case-insensitive)
    tags: list[str] = field(default_factory=list)        # all required
    any_tags: list[str] = field(default_factory=list)    # at least one
    mv_min: float | None = None
    mv_max: float | None = None
    game_changers: str = "any"          # any | exclude | only
    lands: str = "any"                  # any | exclude | only
    commander_able: bool = False
    exclude_names: set[str] = field(default_factory=set)
    min_edhrec_rank: int | None = None  # larger rank = less played; use to hunt obscure cards
    max_edhrec_rank: int | None = None
    released_after: str | None = None
    exclude_rarities: list[str] = field(default_factory=list)  # e.g. ["common"]; rarity of Scryfall's canonical printing
    sort: str = "edhrec"                # edhrec | mv | name | random | relevance | newest
    limit: int | None = 50


def pool(db: CardDB, f: Filters) -> list[Card]:
    where, params = [], []
    join = ""
    if f.text:
        join = "JOIN cards_fts ON cards_fts.rowid = c.rowid"
        where.append("cards_fts MATCH ?")
        params.append(f.text)
    if f.legal_only:
        where.append("c.legal_commander = 'legal'")
    if f.ci_mask is not None:
        where.append("(c.ci_mask & ?) = 0")
        params.append(~f.ci_mask & 31)
    for t in f.types:
        where.append("c.type_line LIKE ?")
        params.append(f"%{t}%")
    for t in f.not_types:
        where.append("c.type_line NOT LIKE ?")
        params.append(f"%{t}%")
    for tag in f.tags:
        where.append("c.oracle_id IN (SELECT oracle_id FROM card_tags WHERE tag = ?)")
        params.append(tag)
    if f.any_tags:
        where.append(f"c.oracle_id IN (SELECT oracle_id FROM card_tags WHERE tag IN ({','.join('?' * len(f.any_tags))}))")
        params += f.any_tags
    if f.mv_min is not None:
        where.append("c.cmc >= ?")
        params.append(f.mv_min)
    if f.mv_max is not None:
        where.append("c.cmc <= ?")
        params.append(f.mv_max)
    if f.game_changers == "exclude":
        where.append("c.game_changer = 0")
    elif f.game_changers == "only":
        where.append("c.game_changer = 1")
    if f.lands == "exclude":
        where.append("c.main_type != 'Land'")
    elif f.lands == "only":
        where.append("c.main_type = 'Land'")
    if f.commander_able:
        where.append("c.commander_role IS NOT NULL")
    if f.min_edhrec_rank is not None:
        where.append("(c.edhrec_rank IS NULL OR c.edhrec_rank >= ?)")
        params.append(f.min_edhrec_rank)
    if f.max_edhrec_rank is not None:
        where.append("c.edhrec_rank <= ?")
        params.append(f.max_edhrec_rank)
    if f.released_after:
        where.append("c.released_at >= ?")
        params.append(f.released_after)
    if f.exclude_rarities:
        where.append(f"c.rarity NOT IN ({','.join('?' * len(f.exclude_rarities))})")
        params += f.exclude_rarities
    order = {
        "edhrec": "COALESCE(c.edhrec_rank, 999999)",
        "mv": "c.cmc, c.name",
        "name": "c.name",
        "newest": "c.released_at DESC",
        "relevance": "bm25(cards_fts)" if f.text else "COALESCE(c.edhrec_rank, 999999)",
        "random": "c.name",
    }.get(f.sort, "COALESCE(c.edhrec_rank, 999999)")
    sql = f"SELECT c.* FROM cards c {join}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order}"
    cards = db.query(sql, params)
    if f.regex:
        rx = re.compile(f.regex, re.I | re.S)
        cards = [c for c in cards if rx.search(c.text) or rx.search(c.type_line)]
    if f.exclude_names:
        ex = {n.lower() for n in f.exclude_names}
        cards = [c for c in cards if c.name.lower() not in ex and c.front_name.lower() not in ex]
    if f.sort == "random":
        random.shuffle(cards)
    if f.limit:
        cards = cards[: f.limit]
    return cards


def scryfall(db: CardDB, query: str, ci_mask: int | None = None, limit: int = 300,
             legal_only: bool = True) -> list[Card]:
    """Run a Scryfall search and return the matching local Card rows (in Scryfall's order)."""
    # Parenthesise the user's query so an appended filter can't bind to only the
    # last branch of a top-level "or" (which silently widens the search).
    q = f"({query})"
    if legal_only and "f:" not in query and "format:" not in query and "legal:" not in query:
        q += " f:commander"
    if ci_mask is not None and "id<=" not in query and "identity" not in query and "ci" not in query.split():
        from .cards import mask_to_str
        q += f" id<={mask_to_str(ci_mask)}"
    limit = limit or 10**9  # 0 = no limit, same as `edh search`
    url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": q, "unique": "cards"})
    out: list[Card] = []
    seen = set()
    while url and len(out) < limit:
        try:
            page = net.get_json(url)
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                return []
            raise
        for sc in page.get("data", []):
            oid = sc.get("oracle_id") or (sc.get("card_faces") or [{}])[0].get("oracle_id")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            c = db.by_oracle(oid)
            if c:
                out.append(c)
        url = page.get("next_page") if page.get("has_more") else None
    return out[:limit]


def ci_from_arg(db: CardDB, spec: str | None) -> int | None:
    """Accept 'WUBG', 'C', or a commander name (or 'A + B' for partners)."""
    if not spec:
        return None
    try:
        return parse_colors(spec)
    except ValueError:
        pass
    mask = 0
    for part in re.split(r"\s*\+\s*", spec):
        mask |= db.require(part).ci_mask
    return mask
