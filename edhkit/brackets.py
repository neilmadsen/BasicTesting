"""Deck legality and Commander Bracket checks.

Bracket definitions follow Wizards' Commander Brackets beta as of the
February 9, 2026 update (53 Game Changers; tutor limits removed in Oct 2025).
Game Changer status comes from Scryfall's `game_changer` field, so it tracks
list updates automatically when the card DB is refreshed.

Combos, mass land denial and extra-turn flags come from Commander Spellbook's
`/estimate-bracket` endpoint (the best public combo database), with a local
fallback when it's unreachable. The *intent* criteria (what a combo does at
what speed, whether extra turns chain) still need the agent's judgement; the
tool surfaces candidates and never pretends to settle them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field

from . import net
from .cards import CardDB
from .deck import BASIC_LANDS, Deck

BRACKETS = {
    1: dict(name="Exhibition", gc_max=0, mld=False, extra_turns="none", two_card_combos="none",
            blurb="Ultra-casual; theme and flavor over function. Games are long; win conditions are thematic."),
    2: dict(name="Core", gc_max=0, mld=False, extra_turns="few, no chaining", two_card_combos="none",
            blurb="Precon-level. Straightforward, unoptimized; games end turn 9+ usually."),
    3: dict(name="Upgraded", gc_max=3, mld=False, extra_turns="low count, no chaining/looping",
            two_card_combos="no early-game two-card infinites; a combo that ends the game around turn 6+ is fine",
            blurb="Beyond precon strength: strong synergy, efficient interaction, up to three Game Changers."),
    4: dict(name="Optimized", gc_max=None, mld=True, extra_turns="allowed", two_card_combos="allowed",
            blurb="High power, no restrictions beyond the banlist; lethal, consistent, fast."),
    5: dict(name="cEDH", gc_max=None, mld=True, extra_turns="allowed", two_card_combos="allowed",
            blurb="Competitive: built to win as efficiently as possible with a metagame in mind."),
}

SPELLBOOK_TAGS = {
    "E": ("Exhibition", 1), "C": ("Core", 2), "O": ("Oddball", 2), "P": ("Powerful", 3),
    "S": ("Spicy", 3), "R": ("Ruthless", 4), "B": ("Banned", None),
}

# Offline fallback when Commander Spellbook is unreachable.
_MLD_NAMES = {
    "Armageddon", "Ravages of War", "Catastrophe", "Decree of Annihilation", "Jokulhaups", "Obliterate",
    "Ruination", "Sunder", "Wildfire", "Burning of Xinye", "Devastation", "Keldon Firebombers",
    "Impending Disaster", "Destructive Force", "Boom // Bust", "Winter Orb", "Static Orb", "Stasis",
    "Blood Moon", "Magus of the Moon", "Back to Basics", "Rising Waters", "Hokori, Dust Drinker",
    "Epicenter", "Global Ruin", "Tectonic Break", "Numot, the Devastator", "Contamination",
    "Infernal Darkness", "Apocalypse", "Upheaval",
}
_MLD_RX = re.compile(r"destroy all lands|each player sacrifices (?:all|\w+) lands|return all lands", re.I)
_EXTRA_TURN_RX = re.compile(r"takes? an extra turn|extra turn after this one", re.I)
_ANY_NUMBER_RX = re.compile(r"a deck can have (any number|up to (\w+)) of cards named", re.I)
_NUM_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


@dataclass
class Report:
    bracket: int
    errors: list[str] = field(default_factory=list)      # illegal deck
    violations: list[str] = field(default_factory=list)  # legal but outside the bracket
    review: list[str] = field(default_factory=list)      # needs a judgement call
    info: list[str] = field(default_factory=list)
    game_changers: list[str] = field(default_factory=list)
    combos: list[dict] = field(default_factory=list)
    spellbook_tag: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors and not self.violations

    def text(self) -> str:
        b = BRACKETS[self.bracket]
        L = [f"Bracket {self.bracket} ({b['name']}) check: " + ("PASS" if self.ok else "FAIL")
             + (" — with items to review" if self.review else "")]
        for title, items in (("ERRORS (deck is not legal)", self.errors), ("BRACKET VIOLATIONS", self.violations),
                             ("REVIEW (judgement call)", self.review), ("info", self.info)):
            if items:
                L.append(f"  {title}:")
                L += [f"    - {x}" for x in items]
        return "\n".join(L)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("bracket", "errors", "violations", "review", "info",
                                               "game_changers", "combos", "spellbook_tag")} | {"ok": self.ok}


def _commander_pair_ok(a, b) -> tuple[bool, str]:
    ta, tb = a.text, b.text
    ka, kb = set(a.keywords), set(b.keywords)
    if re.search(rf"partner with {re.escape(b.front_name)}", ta, re.I) and re.search(rf"partner with {re.escape(a.front_name)}", tb, re.I):
        return True, "Partner with"
    plain = lambda t: bool(re.search(r"(^|\n)partner(\s*\(|$|\n)", t, re.I))
    if plain(ta) and plain(tb):
        return True, "Partner"
    for variant in re.findall(r"partner[—-]([^\n(]+)", ta, re.I):
        if re.search(rf"partner[—-]{re.escape(variant.strip())}", tb, re.I):
            return True, f"Partner—{variant.strip()}"
    if "Friends forever" in ka and "Friends forever" in kb:
        return True, "Friends forever"
    if ("choose a background" in ta.lower() and b.commander_role == "background") or \
       ("choose a background" in tb.lower() and a.commander_role == "background"):
        return True, "Choose a Background"
    if ("doctor's companion" in ta.lower() and "Time Lord Doctor" in b.type_line) or \
       ("doctor's companion" in tb.lower() and "Time Lord Doctor" in a.type_line):
        return True, "Doctor's companion"
    return False, ""


def spellbook_estimate(deck: Deck) -> dict | None:
    body = {
        "commanders": [{"card": e.name, "quantity": 1} for e in deck.commanders],
        "main": [{"card": e.name, "quantity": e.qty} for e in deck.main],
    }
    key = "spellbook-" + hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
    try:
        return net.cached_json(key, lambda: net.post_json("https://backend.commanderspellbook.com/estimate-bracket", body),
                               max_age_days=14)
    except Exception as e:  # network down, API change: fall back to local checks
        return {"_error": str(e)}


def validate(deck: Deck, bracket: int, db: CardDB, use_spellbook: bool = True) -> Report:
    r = Report(bracket=bracket)
    errs = deck.resolve(db)
    r.errors += errs
    if errs:
        return r
    b = BRACKETS[bracket]

    # ---- commanders
    cmdrs = [e.card for e in deck.commanders]
    if not cmdrs:
        r.errors.append("no commander found (add a '# Commander' section)")
    elif len(cmdrs) > 2:
        r.errors.append(f"{len(cmdrs)} commanders listed; max is 2 (partners/backgrounds)")
    for c in cmdrs:
        if c.commander_role is None:
            r.errors.append(f"{c.name} can't be a commander")
    if len(cmdrs) == 2:
        ok, how = _commander_pair_ok(cmdrs[0], cmdrs[1])
        if ok:
            r.info.append(f"commander pair valid via {how}")
        else:
            r.errors.append(f"{cmdrs[0].name} + {cmdrs[1].name} is not a recognised partner/background pair (verify manually if a new partner variant)")
    if len(cmdrs) == 1 and cmdrs[0].commander_role == "background":
        r.errors.append("a Background can only be a commander alongside a creature with 'Choose a Background'")

    # ---- size, singleton, identity, legality
    size = deck.size()
    if size != 100:
        r.errors.append(f"deck has {size} cards including commander(s); needs exactly 100")
    mask = deck.color_identity_mask()
    counts: Counter = Counter()
    for e in deck.commanders + deck.main:
        counts[e.card.name] += e.qty
    for name, n in counts.items():
        card = db.get(name)
        if n > 1 and name not in BASIC_LANDS:
            m = _ANY_NUMBER_RX.search(card.text)
            if not m:
                r.errors.append(f"{name} x{n}: singleton violation")
            elif m.group(2) and n > _NUM_WORDS.get(m.group(2).lower(), 99):
                r.errors.append(f"{name} x{n}: exceeds its own limit ({m.group(2)})")
    for e in deck.commanders + deck.main:
        c = e.card
        if c.ci_mask & ~mask:
            r.errors.append(f"{c.name} ({c.color_identity}) is outside the commander color identity")
        if c.legal_commander == "banned":
            r.errors.append(f"{c.name} is banned in Commander")
        elif c.legal_commander != "legal":
            r.errors.append(f"{c.name} is not legal in Commander ({c.legal_commander})")

    # ---- game changers
    r.game_changers = sorted({c.name for c in deck.cards() if c.game_changer})
    gc_max = b["gc_max"]
    if gc_max is not None and len(r.game_changers) > gc_max:
        r.violations.append(f"{len(r.game_changers)} Game Changers (max {gc_max}): {', '.join(r.game_changers)}")
    elif r.game_changers:
        r.info.append(f"Game Changers ({len(r.game_changers)}): {', '.join(r.game_changers)}")

    # ---- spellbook: MLD, extra turns, combos
    sb = spellbook_estimate(deck) if use_spellbook else None
    mld, extra = set(), set()
    if sb and "_error" not in sb:
        for ce in sb.get("cards", []):
            nm = ce["card"]["name"]
            if ce.get("massLandDenial"):
                mld.add(nm)
            if ce.get("extraTurn"):
                extra.add(nm)
        tag = sb.get("bracketTag")
        if tag:
            label, est = SPELLBOOK_TAGS.get(tag, (tag, None))
            r.spellbook_tag = f"{tag} ({label})"
            r.info.append(f"Commander Spellbook combo-based estimate: {label}" + (f" (≈bracket {est}+)" if est else ""))
        for cb in sb.get("combos", []):
            combo = cb.get("combo", {})
            pieces = [u["card"]["name"] for u in combo.get("uses", [])]
            produces = [p["feature"]["name"] for p in combo.get("produces", [])][:4]
            mv = sum((db.get(p).cmc if db.get(p) else 0) for p in pieces)
            info = {
                "pieces": pieces, "produces": produces, "two_card": bool(cb.get("definitelyTwoCard")),
                "arguably_two_card": bool(cb.get("arguablyTwoCard")), "total_mv": mv,
                "mana_needed": combo.get("manaNeeded"), "prerequisites": combo.get("easyPrerequisites") or combo.get("notablePrerequisites"),
                "bracket_tag": combo.get("bracketTag"), "relevant": cb.get("relevant"),
                "id": combo.get("id"),
            }
            r.combos.append(info)
    else:
        if sb and "_error" in sb:
            r.info.append(f"Commander Spellbook unavailable ({sb['_error'][:80]}); using local MLD/extra-turn heuristics, combos NOT checked")
        for c in deck.cards():
            if c.name in _MLD_NAMES or _MLD_RX.search(c.text):
                mld.add(c.name)
            if _EXTRA_TURN_RX.search(c.text):
                extra.add(c.name)

    if mld:
        # Spellbook's flag is broad (it catches e.g. planeswalker ultimates); only the
        # unmistakable land-denial cards count as hard violations below bracket 4.
        clear = {n for n in mld if n in _MLD_NAMES or _MLD_RX.search((db.get(n).text if db.get(n) else ""))}
        fuzzy = mld - clear
        if b["mld"]:
            r.info.append(f"mass land denial: {', '.join(sorted(mld))}")
        else:
            if clear:
                r.violations.append(f"mass land denial: {', '.join(sorted(clear))}")
            if fuzzy:
                r.review.append(f"flagged as possible land denial by Commander Spellbook (often via an ultimate or rare mode): "
                                f"{', '.join(sorted(fuzzy))} — fine unless it's realistically a land-denial plan")
    if extra:
        if bracket == 1:
            r.violations.append(f"extra turns in an Exhibition deck: {', '.join(sorted(extra))}")
        elif bracket in (2, 3):
            msg = f"extra-turn cards ({len(extra)}): {', '.join(sorted(extra))} — fine in small numbers if they can't chain or loop"
            (r.violations if len(extra) > (2 if bracket == 2 else 3) else r.review).append(msg)
        else:
            r.info.append(f"extra-turn cards: {', '.join(sorted(extra))}")

    for cb in r.combos:
        line = f"{' + '.join(cb['pieces'])} → {', '.join(cb['produces'])} (total MV {cb['total_mv']:g})"
        if cb["two_card"] or (cb["arguably_two_card"] and len(cb["pieces"]) <= 2):
            if bracket <= 2:
                r.violations.append(f"two-card combo: {line}")
            elif bracket == 3:
                early = cb["total_mv"] <= 7
                (r.violations if early else r.review).append(
                    f"two-card combo{' (cheap → likely early-game)' if early else ''}: {line}")
            else:
                r.info.append(f"two-card combo: {line}")
        elif cb.get("relevant"):
            if bracket <= 2:
                r.review.append(f"multi-card combo present (fine if not the deck's plan): {line}")
            else:
                r.info.append(f"combo: {line}")
    return r
