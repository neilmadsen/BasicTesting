"""EDHREC as a *baseline*, not an oracle.

We use it for three things:
  - what the crowd already plays with a commander (so "hidden gem" can be
    defined as: strong fit by our own screening, low inclusion on EDHREC),
  - the popular themes for a commander (a starting map of the strategy space),
  - average decks per bracket, which make decent sparring partners for Forge.
"""

from __future__ import annotations

import re
import unicodedata

from . import net
from .deck import Deck, Entry

BRACKET_SLUG = {1: "exhibition", 2: "core", 3: "upgraded", 4: "optimized", 5: "cedh"}


def slug(name: str) -> str:
    name = name.split(" // ")[0]
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"['’\",.!?:()]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def commander_slug(names: list[str]) -> str:
    if len(names) == 1:
        return slug(names[0])
    return "-".join(sorted(slug(n) for n in names))


def _get(path: str, max_age_days: float = 7):
    url = f"https://json.edhrec.com/pages/{path}.json"
    return net.cached_json(f"edhrec-{path}", lambda: net.get_json(url), max_age_days=max_age_days)


def commander_page(names: list[str], bracket: int | None = None) -> dict:
    s = commander_slug(names)
    path = f"commanders/{s}" + (f"/{BRACKET_SLUG[bracket]}" if bracket else "")
    try:
        raw = _get(path)
    except RuntimeError as e:
        if "404" in str(e) or "403" in str(e):
            return {"slug": s, "found": False, "num_decks": 0, "themes": [], "cards": {}}
        raise
    jd = raw.get("container", {}).get("json_dict", {})
    cards: dict[str, dict] = {}
    for cl in jd.get("cardlists", []):
        for cv in cl.get("cardviews", []):
            pot = cv.get("potential_decks") or 0
            num = cv.get("num_decks") or 0
            cards.setdefault(cv["name"], {
                "inclusion": (num / pot) if pot else None,
                "synergy": cv.get("synergy"),
                "num_decks": num,
                "list": cl.get("header"),
            })
    card = jd.get("card", {}) or {}
    return {
        "slug": s,
        "found": True,
        "num_decks": card.get("num_decks") or raw.get("num_decks_avg"),
        "themes": [(t.get("value"), t.get("count")) for t in raw.get("tag_counts", [])][:25],
        "bracket_counts": raw.get("bracket_counts"),
        "cards": cards,
    }


def average_deck(names: list[str], bracket: int | None = None) -> Deck:
    s = commander_slug(names)
    path = f"average-decks/{s}" + (f"/{BRACKET_SLUG[bracket]}" if bracket else "")
    raw = _get(path)
    d = raw["deck"]
    deck = Deck(title=raw.get("header", s))
    cmdrs = [n for n, _ in d.get("commander_v2", [])] or d.get("commander", [])
    deck.commanders = [Entry(name=n) for n in cmdrs]
    for group in d.get("cards", {}).values():
        for n, q in group:
            deck.main.append(Entry(name=n, qty=int(q)))
    return deck


def top_commanders(period: str = "year", limit: int = 100) -> list[tuple[str, int]]:
    raw = _get(f"commanders/{period}", max_age_days=30)
    out = []
    for cl in raw.get("container", {}).get("json_dict", {}).get("cardlists", []):
        for cv in cl.get("cardviews", []):
            out.append((cv["name"], cv.get("num_decks") or 0))
    out.sort(key=lambda x: -x[1])
    return out[:limit]
