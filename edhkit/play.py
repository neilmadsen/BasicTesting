"""Play a deck yourself in Forge's desktop UI, with every decision recorded.

    ./edh play decks/obeka-splitter-of-seconds/many-mornings/deck.txt [--bracket 3]
    ./edh play --show decks/obeka-splitter-of-seconds/many-mornings/human/<session>

`./edh play` writes Forge deck files for the deck and the bracket's gauntlet (named "EDH ..." and "Gauntlet ...",
so they sort together in Forge's deck lists), builds the pilot jar, and opens Forge with the recorder attached
(pilot/src/edh/pilot/RecorderMain.java). Start a Commander game as usual; each game you play appends to
<deck folder>/human/<session>/human_decisions.jsonl and writes the full game log next to it. The records use the
pilot's decision format, so the game digest, `./edh critical` and the executor comparisons read them like a
piloted run.

`--show` prints a recorded session as one line per decision: the board in brief, what was on offer, what you did.
"""
from __future__ import annotations

import json
import re
import os
import subprocess
import time
from pathlib import Path

from . import forge
from .cards import CardDB
from .deck import Deck

JAVA_XMX = os.environ.get("EDH_PLAY_XMX", "4g")


def deck_label(deck_path: Path) -> str:
    """'EDH - Obeka, Splitter of Seconds - many-mornings' (commander, then the deck's folder)."""
    d = Deck.load(deck_path)
    cmd = " + ".join(e.name for e in d.commanders) or deck_path.parent.name
    return f"EDH - {cmd} - {deck_path.parent.name}"


def write_decks(deck_path: Path, bracket: int, out: Path) -> list[Path]:
    """Our deck first, then the gauntlet, as .dck files in `out`. Returns the paths."""
    out.mkdir(parents=True, exist_ok=True)
    db = CardDB()
    idx = forge.build_card_index()
    paths = []
    ours = forge._load_any_deck(deck_path, db)
    text, subs = forge.forge_deck_text(ours, deck_label(deck_path), idx)
    if subs:
        print(f"note: Forge lacks {len(subs)} card(s) in your deck, replaced by basics: {', '.join(subs)}")
    p = out / f"EDH - {deck_path.parent.name}.dck"
    p.write_text(text)
    paths.append(p)
    for g in forge.load_gauntlet(bracket):
        d = forge._load_any_deck(g, db)
        name = f"Gauntlet B{bracket} - " + (" + ".join(e.name for e in d.commanders) or g.stem)
        text, _ = forge.forge_deck_text(d, name, idx)
        p = out / f"{name.replace('/', '-')}.dck"
        p.write_text(text)
        paths.append(p)
    return paths


def forge_jvm_args() -> list[str]:
    """The JVM flags Forge's own launcher passes. Its jar declares the --add-opens in its manifest, which only
    `java -jar` reads; we run with -cp (Forge plus the recorder), so they're passed explicitly. Without them
    Forge's UI fails while loading its gauntlet files (XStream reflection) and never finishes starting."""
    args = ["-Dio.netty.tryReflectionSetAccessible=true", "-Dfile.encoding=UTF-8"]
    pom = forge.forge_src() / "forge-gui-desktop" / "pom.xml"
    m = re.search(r"<addopen.java.args>(.*?)</addopen.java.args>", pom.read_text()) if pom.exists() else None
    opens = m.group(1).split() if m else ["--add-opens", "java.base/java.util=ALL-UNNAMED",
                                           "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                                           "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
                                           "--add-opens", "java.desktop/java.awt=ALL-UNNAMED",
                                           "--add-opens", "java.desktop/javax.swing=ALL-UNNAMED"]
    return args + opens


def java_cmd(main_args: list[str], headless: bool = False) -> list[str]:
    jar = forge.find_jar()
    if not jar:
        raise SystemExit("Forge isn't built. Run `./edh forge setup` first (about 10 minutes).")
    pilot = forge.build_pilot()
    cmd = ["java", f"-Xmx{JAVA_XMX}", *forge_jvm_args()]
    if headless:
        cmd.append("-Djava.awt.headless=true")
    return cmd + ["-cp", os.pathsep.join([str(jar), str(pilot)]), "edh.pilot.RecorderMain", *main_args]


def session_dir(deck_path: Path) -> Path:
    return deck_path.resolve().parent / "human" / time.strftime("%Y%m%d-%H%M%S")


def launch(deck_path: Path, bracket: int = 3, out: Path | None = None) -> int:
    out = out or session_dir(deck_path)
    decks = out / "decks"
    paths = write_decks(deck_path, bracket, decks)
    print(f"Decks: {paths[0].stem} and {len(paths) - 1} gauntlet decks (installed into Forge's Commander decks).")
    print(f"Recording to {out}")
    print("In Forge: Constructed (or Commander) > choose 'EDH - ...' for yourself and 'Gauntlet ...' decks for the AI seats.")
    cmd = java_cmd(["--out", str(out), "--decks", str(decks)])
    r = subprocess.run(cmd, cwd=forge.res_dir())
    rec = out / "human_decisions.jsonl"
    if rec.exists():
        n = sum(1 for _ in rec.open())
        print(f"\nRecorded {n} records in {rec}\nSummary: ./edh play --show {out}")
    return r.returncode


# --------------------------------------------------------------------------- reading a session

def load(path: Path) -> list[dict]:
    f = path / "human_decisions.jsonl" if path.is_dir() else path
    return [json.loads(line) for line in f.open() if line.strip()]


def _brief_board(state: dict) -> str:
    me = next((p for p in state.get("players", []) if p.get("is_me")), {})
    lives = ", ".join(f"{'us' if p.get('is_me') else p['name']} {p.get('life')}" for p in state.get("players", []))
    return (f"hand {len(state.get('my_hand', []))}, mana {state.get('my_mana_available')}, "
            f"{len(me.get('battlefield', []))} permanents; life: {lives}")


def show(path: Path, all_passes: bool = False) -> str:
    """One line per decision. Passes with nothing castable are skipped unless all_passes."""
    out = []
    for r in load(path):
        t = r.get("type")
        if t == "game_start":
            ps = ", ".join(f"{p['name']} ({' + '.join(p['commanders'])})" + (" [you]" if p["is_me"] else "")
                           for p in r["players"])
            out.append(f"\n=== {r['game']}: {ps}")
        elif t == "outcome":
            out.append(f"=== {r['game']} over on turn {r['turn']}: winner {r['winner']}"
                       f"{' (you)' if r.get('we_won') else ''}; {r.get('records')} records, "
                       f"{r.get('recorder_errors')} recorder errors")
        elif t == "decision":
            q = r["questions"][0]
            a = r["answers"][0]
            opts = [o for o in q["options"] if o["id"] not in ("pass", "none", "keep", "mulligan")]
            if a["choice"] in ("pass", "none") and not opts and not all_passes:
                continue  # nothing was possible: a pass with nothing castable, no creature to attack or block with
            head = f"T{r['turn']} {r['phase']:<22} {r['kind']:<8}"
            took = f"  [{r['ms'] / 1000:.1f}s]" if r.get("ms") is not None else ""
            line = f"{head} -> {a['label']}{took}"
            if r["kind"] in ("action", "attack", "block") and opts:
                names = "; ".join(o["text"].split(":")[0] for o in opts[:8]) + (" ..." if len(opts) > 8 else "")
                line += f"\n{'':40}could: {names}"
            if r.get("state") and r["kind"] in ("action", "mulligan") and (a["choice"] != "pass" or opts):
                line += f"\n{'':40}board: {_brief_board(r['state'])}"
            ctx = (r.get("context") or {}).get("window")
            if ctx and r["kind"] == "action" and not ctx.startswith("our main"):
                line += f"\n{'':40}when: {ctx[:150]}"
            out.append(line)
        elif t == "mulligan":
            out.append(f"T{r['turn']} mulligan")
    return "\n".join(out)


# --------------------------------------------------------------------------- checking a recording

_ID = re.compile(r" \(\d+\)")


def verify(path: Path) -> list[dict]:
    """Reconcile each recorded game with Forge's own log of it. Per game: our casts, activations and land drops
    in the log against the recorded plays (same count, same cards, same order); our attacking and blocking
    creatures against the recorded attacks and blocks; every recorded choice is one of its options; an outcome
    record with no recorder errors."""
    folder = path if path.is_dir() else path.parent
    games: dict[str, list[dict]] = {}
    for r in load(path):
        games.setdefault(r["game"], []).append(r)
    out = []
    for gid, rs in games.items():
        start = next((r for r in rs if r["type"] == "game_start"), {})
        me = start.get("me_name", "")
        log_path = folder / f"{gid}.log"
        log = log_path.read_text().splitlines() if log_path.exists() else []
        q = re.escape(me)
        log_plays = []
        for line in log:
            m = (re.match(rf"Add To Stack: {q} (cast|activated) (.+?)(?: targeting .*)?$", line)
                 or re.match(rf"Land: {q} played (.+)$", line))
            if m:
                log_plays.append(_ID.sub("", m.groups()[-1]).strip())
        dec = [r for r in rs if r["type"] == "decision"]
        rec_plays = [r["answers"][0]["label"] for r in dec if r["kind"] == "action" and r["answers"][0]["choice"] != "pass"]
        misordered = [(a, b) for a, b in zip(log_plays, rec_plays) if a.split(" - ")[0] not in b]
        # one combat log entry spans several lines; only its first carries the "Combat: " prefix
        n_att_log = sum(len(_ID.findall(line.split(" to attack ")[0]))
                        for line in log if re.match(rf"(?:Combat: )?{q} assigned .+ to attack ", line))
        n_blk_log = sum(len(_ID.findall(line.split(" to block ")[0]))
                        for line in log if re.match(rf"(?:Combat: )?{q} assigned .+ to block ", line))

        def n_chosen(kind):
            return sum(len(r["answers"][0]["choice"].split(",")) for r in dec
                       if r["kind"] == kind and r["answers"][0]["choice"] != "none")
        off_menu = [r for r in dec if any(c not in {o["id"] for o in r["questions"][0]["options"]} | {"other"}
                                          for c in r["answers"][0]["choice"].split(","))]
        outcome = next((r for r in rs if r["type"] == "outcome"), None)
        checks = {
            "plays: log vs recorded": (len(log_plays), len(rec_plays)),
            "plays in the same order": not misordered,
            "plays matched to an offered option": sum(r["answers"][0]["choice"] not in ("pass", "other")
                                                     for r in dec if r["kind"] == "action"),
            "attackers: log vs recorded": (n_att_log, n_chosen("attack")),
            "blockers: log vs recorded": (n_blk_log, n_chosen("block")),
            "choices off the option list": len(off_menu),
            "outcome recorded": outcome is not None,
            "recorder errors": outcome.get("recorder_errors") if outcome else None,
        }
        ok = (len(log_plays) == len(rec_plays) and not misordered and n_att_log == n_chosen("attack")
              and n_blk_log == n_chosen("block") and not off_menu and outcome is not None
              and outcome.get("recorder_errors") == 0 and bool(log))
        out.append({"game": gid, "ok": ok, "decisions": len(dec), "checks": checks,
                    "misordered": misordered[:5], "log_found": bool(log)})
    return out
