"""Decklists: parse the formats people paste, write a canonical annotated format.

Canonical format (what the agents write and what `edh deck fmt` produces):

    # Commander
    1 Atraxa, Praetors' Voice

    # Creatures (24)
    1 Evolution Sage  # engine: proliferate on every land drop
    ...

Anything after " # " on a card line is an annotation (role, reason, "GEM"),
preserved through formatting. Lines starting with "#" or "//" are headers or
comments. Recognised headers: Commander(s), Deck/Main/Mainboard (+ any type
group like "Creatures"), Maybe/Maybeboard/Considering/Sideboard (ignored for
legality, kept for reference).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .cards import Card, CardDB, TYPE_ORDER

BASIC_LANDS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes",
}

_LINE = re.compile(r"^\s*(?:(\d+)\s*[xX]?\s+)?(.+?)\s*$")
_SET_SUFFIX = re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(\s+[\w\-★]+)?(\s+\*[A-Z]\*)*\s*$")
_FORGE_SUFFIX = re.compile(r"\|[A-Za-z0-9]+(\|\d+)?$")

SECTION_ALIASES = {
    "commander": "commander", "commanders": "commander", "command zone": "commander",
    "deck": "main", "main": "main", "mainboard": "main", "main deck": "main", "library": "main",
    "maybe": "maybe", "maybeboard": "maybe", "considering": "maybe", "sideboard": "maybe",
    "companion": "maybe", "tokens": "ignore",
}


@dataclass
class Entry:
    name: str
    qty: int = 1
    note: str = ""
    card: Card | None = None


@dataclass
class Deck:
    commanders: list[Entry] = field(default_factory=list)
    main: list[Entry] = field(default_factory=list)
    maybe: list[Entry] = field(default_factory=list)
    title: str = ""
    header_comments: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ parsing
    @classmethod
    def parse(cls, text: str) -> "Deck":
        deck = cls()
        section = "main"
        for raw in text.splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            # [Commander] / [Main] (Forge .dck), plus [metadata] Name=
            if stripped.startswith("[") and stripped.endswith("]"):
                sec = stripped[1:-1].strip().lower()
                section = SECTION_ALIASES.get(sec, "ignore" if sec == "metadata" else "main")
                continue
            if stripped.lower().startswith("name=") and section == "ignore":
                deck.title = stripped[5:]
                continue
            if stripped.startswith(("#", "//")):
                head = stripped.lstrip("#/ ").strip()
                key = re.sub(r"\s*\(\d+\)\s*$", "", head).strip().rstrip(":").lower()
                if key in SECTION_ALIASES:
                    section = SECTION_ALIASES[key]
                elif any(key.startswith(t.lower()) for t in TYPE_ORDER + ["lands", "creatures", "artifacts", "enchantments", "instants", "sorceries", "planeswalkers", "battles", "other"]):
                    if section in ("commander", "ignore"):
                        section = "main"
                elif not deck.commanders and not deck.main:
                    deck.header_comments.append(head)
                continue
            m = re.match(r"^(commander|deck|mainboard|sideboard|maybeboard)\s*:?\s*$", stripped, re.I)
            if m:
                section = SECTION_ALIASES[m.group(1).lower()]
                continue
            if section == "ignore":
                continue
            note = ""
            if " # " in line or "\t# " in line:
                line, note = re.split(r"\s#\s", line, maxsplit=1)
            stripped = line.strip()
            m = _LINE.match(stripped)
            if not m:
                continue
            qty = int(m.group(1) or 1)
            name = m.group(2)
            name = _FORGE_SUFFIX.sub("", name)
            name = _SET_SUFFIX.sub("", name)
            name = re.sub(r"\s*\*CMDR\*\s*$", "", name, flags=re.I)
            is_cmdr_marker = bool(re.search(r"\*CMDR\*|\[commander\]", stripped, re.I))
            name = re.sub(r"\s*\[commander\]\s*$", "", name, flags=re.I).strip()
            entry = Entry(name=name, qty=qty, note=note.strip())
            target = "commander" if is_cmdr_marker else section
            getattr(deck, {"commander": "commanders", "main": "main", "maybe": "maybe"}[target]).append(entry)
        return deck

    @classmethod
    def load(cls, path: str | Path) -> "Deck":
        p = Path(path)
        d = cls.parse(p.read_text())
        if not d.title:
            d.title = p.parent.name if p.stem in ("deck", "list") else p.stem
        return d

    # ------------------------------------------------------------------ resolution
    def resolve(self, db: CardDB) -> list[str]:
        """Attach Card objects. Returns a list of error strings for unknown names."""
        errors = []
        for e in self.commanders + self.main + self.maybe:
            if e.card is None:
                e.card = db.get(e.name)
                if e.card is None:
                    sugg = db.suggest(e.name)
                    errors.append(f"unknown card: {e.name!r}" + (f" (did you mean {', '.join(sugg[:3])}?)" if sugg else ""))
                else:
                    e.name = e.card.name
        return errors

    # ------------------------------------------------------------------ helpers
    def cards(self, include_commanders: bool = True) -> list[Card]:
        out = []
        for e in (self.commanders if include_commanders else []) + self.main:
            if e.card:
                out.extend([e.card] * e.qty)
        return out

    def size(self) -> int:
        return sum(e.qty for e in self.commanders + self.main)

    def names(self) -> set[str]:
        return {e.name for e in self.commanders + self.main}

    def color_identity_mask(self) -> int:
        m = 0
        for e in self.commanders:
            if e.card:
                m |= e.card.ci_mask
        return m

    def promote_commander(self, name: str) -> None:
        """Move a main-deck entry into the command zone (for lists pasted without a header)."""
        e = self.entry(name)
        if e is None:
            self.commanders.append(Entry(name=name))
        elif e not in self.commanders:
            self.main.remove(e)
            self.commanders.append(e)

    def entry(self, name: str) -> Entry | None:
        low = name.lower()
        for e in self.commanders + self.main:
            if e.name.lower() == low or (e.card and (e.card.front_name.lower() == low)):
                return e
        return None

    # ------------------------------------------------------------------ writing
    def to_text(self, group: bool = True) -> str:
        out = []
        if self.header_comments:
            out += [f"# {c}" for c in self.header_comments] + [""]
        out.append("# Commander")
        for e in self.commanders:
            out.append(_fmt(e))
        out.append("")
        if group and all(e.card for e in self.main):
            groups: dict[str, list[Entry]] = {}
            for e in self.main:
                groups.setdefault(e.card.main_type, []).append(e)  # type: ignore[union-attr]
            for t in TYPE_ORDER[1:] + ["Other", "Land"]:
                es = groups.get(t)
                if not es:
                    continue
                label = {"Other": "Other"}.get(t, t + ("s" if not t.endswith("y") else ""))
                if t == "Sorcery":
                    label = "Sorceries"
                out.append(f"# {label} ({sum(e.qty for e in es)})")
                key = (lambda e: (e.card.cmc, e.name)) if t != "Land" else (lambda e: (e.name in BASIC_LANDS, e.name))
                for e in sorted(es, key=key):
                    out.append(_fmt(e))
                out.append("")
        else:
            out.append("# Deck")
            out += [_fmt(e) for e in self.main]
            out.append("")
        if self.maybe:
            out.append("# Maybeboard")
            out += [_fmt(e) for e in self.maybe]
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def to_plain(self) -> str:
        """Plain 'N Name' list (commanders first) — pastes into Moxfield/Archidekt/MPCFill/proxy sites."""
        lines = [f"{e.qty} {e.name}" for e in self.commanders]
        lines += [f"{e.qty} {e.name}" for e in sorted(self.main, key=lambda e: e.name)]
        return "\n".join(lines) + "\n"

    def to_forge(self, name: str | None = None) -> str:
        def fname(e: Entry) -> str:
            return e.card.forge_name if e.card else e.name
        lines = ["[metadata]", f"Name={name or self.title or 'Deck'}", "[Commander]"]
        lines += [f"{e.qty} {fname(e)}" for e in self.commanders]
        lines.append("[Main]")
        lines += [f"{e.qty} {fname(e)}" for e in self.main]
        return "\n".join(lines) + "\n"


def _fmt(e: Entry) -> str:
    s = f"{e.qty} {e.name}"
    return f"{s}  # {e.note}" if e.note else s


def load_resolved(path: str | Path, db: CardDB) -> Deck:
    deck = Deck.load(path)
    errs = deck.resolve(db)
    if errs:
        raise SystemExit("\n".join(errs))
    return deck
