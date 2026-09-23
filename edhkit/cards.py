"""Local card database built once from Scryfall's Oracle Cards bulk file.

One row per Oracle ID (i.e. per distinct card, not per printing), with the
fields deckbuilding actually needs, an FTS5 index over name/type/text, a name
alias table for forgiving lookups, and a tag table filled by `edh tags`.
"""

from __future__ import annotations

import gzip
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from . import net
from .paths import CARDS_DB, SCRYFALL_DIR, ensure_dirs

BULK_META_URL = "https://api.scryfall.com/bulk-data/oracle-cards"
SKIP_LAYOUTS = {
    "token", "double_faced_token", "emblem", "art_series", "vanguard",
    "scheme", "planar", "front_card",
}
COLOR_BITS = {"W": 1, "U": 2, "B": 4, "R": 8, "G": 16}
WUBRG = "WUBRG"
TYPE_ORDER = ["Land", "Creature", "Planeswalker", "Battle", "Artifact", "Enchantment", "Instant", "Sorcery"]
# Forge (and every decklist site) names split/aftermath cards "A // B" but
# everything else with two faces by its front face.
FULL_NAME_LAYOUTS = {"split", "aftermath"}


# --------------------------------------------------------------------------- helpers

def fold(name: str) -> str:
    """Lowercase, strip accents and punctuation variants for lookups."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def ci_mask(colors: Iterable[str]) -> int:
    m = 0
    for c in colors:
        m |= COLOR_BITS.get(c.upper(), 0)
    return m


def mask_to_str(mask: int) -> str:
    return "".join(c for c in WUBRG if mask & COLOR_BITS[c]) or "C"


def parse_colors(spec: str) -> int:
    """'BG', 'golgari'-free: accepts letters only; 'C' or '' means colorless."""
    spec = spec.strip().upper()
    if spec in ("", "C", "COLORLESS"):
        return 0
    bad = set(spec) - set(WUBRG)
    if bad:
        raise ValueError(f"bad color letters {bad!r} in {spec!r}; use WUBRG letters")
    return ci_mask(spec)


def main_type(type_line: str) -> str:
    front = type_line.split("//")[0]
    for t in TYPE_ORDER:
        if t in front:
            return t
    return "Other"


# --------------------------------------------------------------------------- build

def download_bulk(force: bool = False) -> Path:
    ensure_dirs()
    dest = SCRYFALL_DIR / "oracle-cards.jsonl.gz"
    meta = net.get_json(BULK_META_URL)
    marker = SCRYFALL_DIR / "oracle-cards.updated_at"
    if dest.exists() and not force and marker.exists() and marker.read_text() == meta["updated_at"]:
        return dest
    url = meta.get("jsonl_download_uri") or meta.get("download_uri")
    if not url:
        raise RuntimeError(f"Scryfall bulk metadata has no download uri: {list(meta)}")
    if url.endswith(".json"):  # legacy array format
        raw = SCRYFALL_DIR / "oracle-cards.json"
        net.download(url, raw)
        with open(raw) as f, gzip.open(dest, "wt") as out:
            for card in json.load(f):
                out.write(json.dumps(card) + "\n")
        raw.unlink()
    else:
        net.download(url, dest)
    marker.write_text(meta["updated_at"])
    return dest


def _iter_bulk(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if line and line not in ("[", "]"):
                yield json.loads(line)


def _faces(c: dict) -> list[dict]:
    return c.get("card_faces") or [c]


def _card_text(c: dict) -> str:
    faces = _faces(c)
    if len(faces) == 1:
        return faces[0].get("oracle_text") or ""
    parts = []
    for f in faces:
        head = f"[{f.get('name')}] {f.get('mana_cost') or ''} — {f.get('type_line') or ''}".strip()
        parts.append(f"{head}\n{f.get('oracle_text') or ''}".strip())
    return "\n//\n".join(parts)


def _images(c: dict) -> tuple[str | None, str | None]:
    if c.get("image_uris"):
        return c["image_uris"].get("large"), None
    faces = c.get("card_faces") or []
    front = faces[0].get("image_uris", {}).get("large") if faces else None
    back = faces[1].get("image_uris", {}).get("large") if len(faces) > 1 else None
    return front, back


def _commander_role(c: dict) -> str | None:
    front = _faces(c)[0]
    tl = front.get("type_line") or c.get("type_line", "")
    text = _card_text(c).lower()
    if "can be your commander" in text:
        return "commander"
    if "Legendary" in tl and ("Creature" in tl):
        return "commander"
    if "Background" in tl and "Legendary" in tl:
        return "background"
    return None


SCHEMA = """
CREATE TABLE cards (
    oracle_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    front_name TEXT NOT NULL,
    forge_name TEXT NOT NULL,
    layout TEXT,
    mana_cost TEXT,
    cmc REAL,
    type_line TEXT,
    main_type TEXT,
    text TEXT,
    power TEXT, toughness TEXT, loyalty TEXT,
    colors TEXT,
    color_identity TEXT,
    ci_mask INTEGER,
    keywords TEXT,
    produced_mana TEXT,
    legal_commander TEXT,
    game_changer INTEGER,
    commander_role TEXT,
    edhrec_rank INTEGER,
    reserved INTEGER,
    released_at TEXT,
    set_code TEXT,
    rarity TEXT,
    image_front TEXT,
    image_back TEXT,
    scryfall_uri TEXT
);
CREATE TABLE names (alias TEXT PRIMARY KEY, oracle_id TEXT NOT NULL, priority INTEGER);
CREATE TABLE card_tags (oracle_id TEXT, tag TEXT, PRIMARY KEY (oracle_id, tag));
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX cards_ci ON cards(ci_mask);
CREATE INDEX cards_type ON cards(main_type);
CREATE INDEX tags_tag ON card_tags(tag);
CREATE VIRTUAL TABLE cards_fts USING fts5(
    name, type_line, text, content='cards', content_rowid='rowid', tokenize='porter unicode61'
);
"""


def build_db(bulk: Path | None = None, db_path: Path = CARDS_DB) -> int:
    bulk = bulk or download_bulk()
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    rows, aliases = [], []
    for c in _iter_bulk(bulk):
        if c.get("layout") in SKIP_LAYOUTS or not c.get("oracle_id"):
            continue
        faces = _faces(c)
        front = faces[0]
        name = c["name"]
        front_name = front.get("name") or name
        forge_name = name if c.get("layout") in FULL_NAME_LAYOUTS else front_name
        img_f, img_b = _images(c)
        type_line = c.get("type_line") or front.get("type_line") or ""
        mana_cost = c.get("mana_cost") if c.get("mana_cost") not in (None, "") else front.get("mana_cost")
        rows.append((
            c["oracle_id"], name, front_name, forge_name, c.get("layout"),
            mana_cost or "", c.get("cmc") or 0.0, type_line, main_type(type_line), _card_text(c),
            front.get("power") or c.get("power"), front.get("toughness") or c.get("toughness"),
            front.get("loyalty") or c.get("loyalty"),
            "".join(c.get("colors") or front.get("colors") or []),
            mask_to_str(ci_mask(c.get("color_identity") or [])),
            ci_mask(c.get("color_identity") or []),
            json.dumps(c.get("keywords") or []),
            "".join(c.get("produced_mana") or []),
            (c.get("legalities") or {}).get("commander", "not_legal"),
            1 if c.get("game_changer") else 0,
            _commander_role(c),
            c.get("edhrec_rank"),
            1 if c.get("reserved") else 0,
            c.get("released_at"), c.get("set"), c.get("rarity"),
            img_f, img_b, c.get("scryfall_uri"),
        ))
        oid = c["oracle_id"]
        aliases.append((fold(name), oid, 0))
        aliases.append((fold(front_name), oid, 1))
        for f in faces[1:]:
            if f.get("name"):
                aliases.append((fold(f["name"]), oid, 2))
        # Common "A/B" and "A // B" spellings for split cards
        if " // " in name:
            aliases.append((fold(name.replace(" // ", "/")), oid, 1))
    con.executemany(f"INSERT INTO cards VALUES ({','.join('?' * 29)})", rows)
    # Lower priority number wins; legal cards beat not-legal duplicates
    # (e.g. Alchemy rebalanced "A-" versions share nothing, but some face names collide).
    aliases.sort(key=lambda a: a[2])
    con.executemany("INSERT OR IGNORE INTO names VALUES (?,?,?)", aliases)
    con.execute("INSERT INTO cards_fts(cards_fts) VALUES ('rebuild')")
    con.execute("INSERT INTO meta VALUES ('built_from', ?)", (str(bulk.name),))
    marker = SCRYFALL_DIR / "oracle-cards.updated_at"
    if marker.exists():
        con.execute("INSERT INTO meta VALUES ('scryfall_updated_at', ?)", (marker.read_text(),))
    con.commit()
    # Preserve tags from an existing DB so a card refresh doesn't force a re-harvest.
    if db_path.exists():
        try:
            con.execute("ATTACH DATABASE ? AS old", (str(db_path),))
            con.execute(
                "INSERT OR IGNORE INTO card_tags SELECT oracle_id, tag FROM old.card_tags "
                "WHERE oracle_id IN (SELECT oracle_id FROM cards)"
            )
            con.execute("INSERT OR REPLACE INTO meta SELECT * FROM old.meta WHERE key LIKE 'tags%'")
            con.commit()
            con.execute("DETACH DATABASE old")
        except sqlite3.Error:
            pass
    con.close()
    tmp.replace(db_path)
    return len(rows)


# --------------------------------------------------------------------------- access

@dataclass
class Card:
    oracle_id: str
    name: str
    front_name: str
    forge_name: str
    layout: str
    mana_cost: str
    cmc: float
    type_line: str
    main_type: str
    text: str
    power: str | None
    toughness: str | None
    loyalty: str | None
    colors: str
    color_identity: str
    ci_mask: int
    keywords: list[str]
    produced_mana: str
    legal_commander: str
    game_changer: bool
    commander_role: str | None
    edhrec_rank: int | None
    reserved: bool
    released_at: str | None
    set_code: str | None
    rarity: str | None
    image_front: str | None
    image_back: str | None
    scryfall_uri: str | None
    tags: list[str] | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Card":
        d = dict(row)
        d["keywords"] = json.loads(d.get("keywords") or "[]")
        d["game_changer"] = bool(d["game_changer"])
        d["reserved"] = bool(d["reserved"])
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    @property
    def is_land(self) -> bool:
        return self.main_type == "Land"

    @property
    def pt(self) -> str:
        if self.power is not None and self.toughness is not None:
            return f"{self.power}/{self.toughness}"
        if self.loyalty:
            return f"[{self.loyalty}]"
        return ""

    def oneline(self, width: int = 160) -> str:
        text = self.text.replace("\n", " ")
        cost = self.mana_cost or ""
        extra = f" {self.pt}" if self.pt else ""
        s = f"{self.name} {cost} | {self.type_line}{extra} | {text}"
        return s if len(s) <= width else s[: width - 1] + "…"

    def full(self) -> str:
        lines = [f"{self.name}  {self.mana_cost}  (mv {self.cmc:g})", self.type_line + (f"  {self.pt}" if self.pt else "")]
        lines.append(self.text)
        meta = [f"CI {self.color_identity}", f"commander:{self.legal_commander}"]
        if self.game_changer:
            meta.append("GAME CHANGER")
        if self.commander_role:
            meta.append(f"can be {self.commander_role}")
        if self.edhrec_rank:
            meta.append(f"EDHREC rank #{self.edhrec_rank}")
        if self.tags:
            meta.append("tags: " + ", ".join(self.tags))
        lines.append(" · ".join(meta))
        return "\n".join(lines)


class CardDB:
    def __init__(self, path: Path = CARDS_DB):
        if not path.exists():
            raise SystemExit(f"card database missing at {path}; run `./edh setup` (or `./edh cards update`)")
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self._cache: dict[str, Card | None] = {}

    def meta(self, key: str) -> str | None:
        r = self.con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r[0] if r else None

    def by_oracle(self, oid: str) -> Card | None:
        r = self.con.execute("SELECT * FROM cards WHERE oracle_id=?", (oid,)).fetchone()
        return self._with_tags(Card.from_row(r)) if r else None

    def get(self, name: str) -> Card | None:
        """Exact-ish lookup: full name, any face name, accent/quote-insensitive."""
        key = fold(name)
        if key in self._cache:
            return self._cache[key]
        r = self.con.execute(
            "SELECT c.* FROM names n JOIN cards c USING (oracle_id) WHERE n.alias=? "
            "ORDER BY (c.legal_commander='legal') DESC, n.priority LIMIT 1",
            (key,),
        ).fetchone()
        card = self._with_tags(Card.from_row(r)) if r else None
        self._cache[key] = card
        return card

    def suggest(self, name: str, limit: int = 5) -> list[str]:
        key = fold(name)
        rows = self.con.execute(
            "SELECT DISTINCT c.name FROM names n JOIN cards c USING (oracle_id) "
            "WHERE n.alias LIKE ? ORDER BY length(n.alias) LIMIT ?",
            (f"%{key}%", limit),
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
        # fall back to FTS on the name column
        words = [w for w in re.findall(r"[a-z0-9]+", key) if len(w) > 2]
        if not words:
            return []
        q = " OR ".join(f"name:{w}" for w in words)
        rows = self.con.execute(
            "SELECT c.name FROM cards_fts f JOIN cards c ON c.rowid=f.rowid WHERE cards_fts MATCH ? "
            "ORDER BY bm25(cards_fts) LIMIT ?",
            (q, limit),
        ).fetchall()
        return [r[0] for r in rows]

    def require(self, name: str) -> Card:
        card = self.get(name)
        if card is None:
            sugg = self.suggest(name)
            hint = f" Did you mean: {', '.join(sugg)}?" if sugg else ""
            raise KeyError(f"unknown card {name!r}.{hint}")
        return card

    def tags_for(self, oid: str) -> list[str]:
        return [r[0] for r in self.con.execute("SELECT tag FROM card_tags WHERE oracle_id=? ORDER BY tag", (oid,))]

    def _with_tags(self, card: Card) -> Card:
        card.tags = self.tags_for(card.oracle_id)
        return card

    def query(self, sql: str, params: Iterable = ()) -> list[Card]:
        return [self._with_tags(Card.from_row(r)) for r in self.con.execute(sql, tuple(params))]

    def count(self) -> int:
        return self.con.execute("SELECT count(*) FROM cards").fetchone()[0]
