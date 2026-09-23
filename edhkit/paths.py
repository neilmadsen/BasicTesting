"""Filesystem layout. Everything generated lives under data/ (gitignored)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("EDH_DATA_DIR", ROOT / "data"))
CACHE = DATA / "cache"
SCRYFALL_DIR = DATA / "scryfall"
CARDS_DB = DATA / "cards.db"
DECKS = ROOT / "decks"
GAUNTLET = ROOT / "gauntlet"

# Forge lives outside the repo by default: it's an 800MB checkout.
FORGE_HOME = Path(os.environ.get("FORGE_HOME", DATA / "forge"))
FORGE_SRC = FORGE_HOME / "src"
FORGE_USER_DIR = FORGE_HOME / "user"


def ensure_dirs() -> None:
    for p in (DATA, CACHE, SCRYFALL_DIR, FORGE_HOME):
        p.mkdir(parents=True, exist_ok=True)
