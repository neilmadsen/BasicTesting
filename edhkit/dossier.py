"""Scouting dossiers on opposing commanders, for the pilot's strategist.

A strong player who sees Sephiroth across the table already knows it drains on
every creature death and flips on the fourth; that Edgar's eminence makes tokens
from the command zone, so killing Edgar doesn't stop them; that Sauron amasses
whenever we cast a spell. The strategist otherwise has only a card name. A
dossier is that table knowledge, written once per commander from public
information (oracle text, EDHREC themes and most-played cards) and cached in
gauntlet/dossiers/. It is deliberately about the commander's typical deck, not
the exact gauntlet list, which a real opponent would not show us.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from .cards import CardDB
from .paths import GAUNTLET

DOSSIER_DIR = GAUNTLET / "dossiers"

SYSTEM = (
    "You are a veteran Commander (EDH) player writing a scouting report on an opposing commander's typical "
    "deck for a teammate who will play against it. Be concrete and card-named; use only what the commander's "
    "text and the deck data support. At most 170 words, plain text, these labelled lines:\n"
    "PLAN: how the deck develops and wins, in one or two sentences.\n"
    "ENGINE: the commander's ability and the 3-6 cards that make the deck dangerous.\n"
    "KILL ON SIGHT: what must be answered immediately and with what kind of answer (exile vs destroy vs "
    "bounce vs counter); say plainly if killing the commander does NOT stop the engine (eminence, recursion, "
    "death triggers).\n"
    "PUNISHES: what our own plays feed (creature deaths, casting spells, attacking it, graveyards, life "
    "loss) so we don't help it.\n"
    "EXPECT: its usual interaction (wipes, spot removal, counters, graveyard hate, theft) and how to play "
    "around it.\n"
    "CLOCK: how fast it typically threatens lethal at a casual-to-focused table, and how (combat, drain, "
    "combo, poison)."
)


def _slug(name: str) -> str:
    from .edhrec import slug
    return slug(name)


def dossier_path(commander: str) -> Path:
    return DOSSIER_DIR / f"{_slug(commander)}.md"


def _inputs(commander: str, db: CardDB, bracket: int | None) -> str:
    from . import edhrec
    card = db.get(commander)
    parts = [f"Commander: {card.full() if card else commander}"]
    try:
        page = edhrec.commander_page([commander], bracket=bracket)
    except Exception as e:  # offline: the model's own knowledge plus the oracle text
        page = {"found": False, "themes": [], "cards": {}, "error": str(e)}
    if page.get("found"):
        parts.append("EDHREC themes (decks): " + ", ".join(f"{t} ({n})" for t, n in page["themes"][:8]))
        ranked = sorted(((n, d) for n, d in page["cards"].items() if (d.get("inclusion") or 0) >= 0.2),
                        key=lambda nd: -(nd[1].get("inclusion") or 0))
        lines = []
        for name, d in ranked[:45]:
            c = db.get(name)
            if c and c.is_land:
                continue
            txt = c.oneline(200) if c else name
            lines.append(f"- {round(100 * (d.get('inclusion') or 0))}% · {txt}")
        parts.append("Most-played non-land cards (inclusion %, oracle):\n" + "\n".join(lines[:35]))
    return "\n\n".join(parts)


INTERACTION = [  # (label, tags): what a strong player expects a deck to be holding
    ("board wipes", {"board-wipe"}),
    ("counterspells", {"counterspell"}),
    ("spot removal", {"spot-removal"}),
    ("artifact/enchantment removal", {"artifact-removal", "enchantment-removal"}),
    ("graveyard hate", {"graveyard-hate"}),
    ("theft", {"theft"}),
    ("protection", {"protection", "gives-indestructible", "gives-hexproof", "fog"}),
    ("tutors", {"tutor"}),
]


def interaction_profile(commander: str, db: CardDB, bracket: int | None = 3, floor: float = 0.15) -> str:
    """Deterministic: per category, the cards the commander's decks usually play (EDHREC inclusion) and
    the expected number of such cards in a typical 99 (sum of inclusion rates)."""
    from . import edhrec
    try:
        page = edhrec.commander_page([commander], bracket=bracket)
    except Exception:
        return ""
    if not page.get("found"):
        return ""
    lines = ["INTERACTION (from EDHREC: expected count in a typical list; most-played with inclusion %):"]
    for label, tags in INTERACTION:
        rows = []
        for name, d in page["cards"].items():
            inc = d.get("inclusion") or 0
            c = db.get(name)
            if c and inc >= floor and tags & set(c.tags or []) and not (label == "tutors" and c.is_land):
                rows.append((inc, name))
        if not rows:
            continue
        rows.sort(reverse=True)
        expected = sum(i for i, _ in rows)
        lines.append(f"- {label} ≈ {expected:.1f}: " + ", ".join(f"{n} {round(100 * i)}%" for i, n in rows[:7]))
    return "\n".join(lines) if len(lines) > 1 else ""


def build(commander: str, db: CardDB, bracket: int | None = 3, model: str = "claude-opus-5-5",
          effort: str = "high") -> str:
    prompt = _inputs(commander, db, bracket) + "\n\nWrite the scouting report."
    out = subprocess.run(
        ["claude", "-p", "--tools", "", "--no-session-persistence", "--effort", effort, "--model", model,
         "--system-prompt", SYSTEM],
        input=prompt, capture_output=True, text=True, timeout=600, cwd=tempfile.gettempdir())
    text = out.stdout.strip()
    if text:
        write(commander, text, interaction_profile(commander, db, bracket))
    return text


def write(commander: str, text: str, profile: str) -> None:
    DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    dossier_path(commander).write_text(f"# {commander}\n\n{text}\n" + (f"\n{profile}\n" if profile else ""))


def refresh_profiles(bracket: int = 3) -> None:
    """Recompute the deterministic INTERACTION section of existing dossiers (no model calls)."""
    db = CardDB()
    for c in dict.fromkeys(gauntlet_commanders(bracket)):
        p = dossier_path(c)
        if p.exists():
            body = p.read_text().split("\n", 2)[-1].split("\nINTERACTION (")[0].strip()
            write(c, body, interaction_profile(c, db, bracket))


def get(commander: str, db: CardDB | None = None, build_missing: bool = False, **kw) -> str:
    """Cached dossier text ('' if none and not building)."""
    p = dossier_path(commander)
    if p.exists():
        return p.read_text().split("\n", 2)[-1].strip()
    if build_missing:
        return build(commander, db or CardDB(), **kw)
    return ""


def gauntlet_commanders(bracket: int) -> list[str]:
    """Commander names in a gauntlet folder (from the .dck [Commander] sections)."""
    names = []
    for f in sorted((GAUNTLET / f"b{bracket}").glob("*.dck")):
        section = None
        for line in f.read_text().splitlines():
            if line.startswith("["):
                section = line.strip("[]").lower()
            elif section == "commander" and line.strip():
                names.append(line.split(" ", 1)[1].split("|")[0].strip())
    return names


if __name__ == "__main__":  # python3 -m edhkit.dossier <bracket> [--profiles-only]
    import sys
    from concurrent.futures import ThreadPoolExecutor
    br = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    db = CardDB()
    if "--profiles-only" in sys.argv:
        refresh_profiles(br)
        sys.exit(0)
    todo = [c for c in dict.fromkeys(gauntlet_commanders(br)) if not dossier_path(c).exists()]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, text in zip(todo, ex.map(lambda c: build(c, db, bracket=br), todo)):
            print(f"{name}: {len(text.split())} words")
    print(json.dumps(sorted(p.name for p in DOSSIER_DIR.glob('*.md'))))
