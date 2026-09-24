"""Forge (github.com/Card-Forge/forge) as a headless Commander simulator.

Forge implements the full rules for ~34k cards and ships an AI that can play
Commander pods from the command line (`forge sim -f commander`). The AI is a
competent *goldfisher with blockers*: it curves out, attacks, removes obvious
threats. It is poor at combo lines, politics, holding up interaction, and
evaluating complicated engines. Treat results as a coarse signal: "does this
deck function and pressure a table of similar-power decks", not "is card X
2% better than card Y".

Mechanics here:
  - each worker gets its own fake $HOME so parallel JVMs don't share ~/.forge
  - a cross-process slot lock caps concurrent JVMs (several agents may sim at once)
  - full game logs are parsed for per-card cast stats, then condensed and saved
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .cards import CardDB
from .deck import BASIC_LANDS, Deck, Entry
from .paths import FORGE_HOME, FORGE_SRC, GAUNTLET, ROOT

JAR_GLOB = "forge-gui-desktop/target/forge-gui-desktop-*-jar-with-dependencies.jar"
SLOTS = int(os.environ.get("EDH_FORGE_SLOTS", max(1, (os.cpu_count() or 2) - 1)))
JAVA_XMX = os.environ.get("EDH_FORGE_XMX", "1536m")


# --------------------------------------------------------------------------- install

def forge_src() -> Path:
    env = os.environ.get("FORGE_SRC")
    return Path(env) if env else FORGE_SRC


def find_jar() -> Path | None:
    src = forge_src()
    jars = sorted(src.glob(JAR_GLOB)) if src.exists() else []
    return jars[-1] if jars else None


def res_dir() -> Path:
    return forge_src() / "forge-gui"


def status() -> dict:
    jar = find_jar()
    java = shutil.which("java")
    ver = ""
    if java:
        try:
            out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=20)
            m = re.search(r'version "([^"]+)"', out.stderr + out.stdout)
            ver = m.group(1) if m else "?"
        except Exception:
            ver = "?"
    return {"java": ver or None, "src": str(forge_src()), "src_exists": forge_src().exists(), "jar": str(jar) if jar else None}


def setup(update: bool = False) -> Path:
    """Clone (shallow) and build Forge. Needs git, Maven, JDK 17+. ~5-10 minutes the first time."""
    src = forge_src()
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        print(f"cloning Forge into {src} (shallow, ~800MB)…", file=sys.stderr)
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Card-Forge/forge", str(src)], check=True, env=env)
    elif update:
        subprocess.run(["git", "-C", str(src), "pull", "--depth", "1", "--rebase=false"], check=True)
    if find_jar() is None or update:
        print("building Forge with Maven (forge-gui-desktop and deps)…", file=sys.stderr)
        subprocess.run(["mvn", "-B", "-q", "-pl", "forge-gui-desktop", "-am", "-DskipTests",
                        "-Dcheckstyle.skip", "-Dmaven.javadoc.skip=true", "package"], cwd=src, check=True)
    jar = find_jar()
    if not jar:
        raise SystemExit("Forge build finished but no jar-with-dependencies was found")
    build_card_index(force=True)
    return jar


PILOT_SRC = ROOT / "pilot" / "src"
# EDH_PILOT_JAR lets an experimental build live beside the one a running sim is using: every pod starts a
# fresh JVM, so rebuilding the default jar mid-run would change the pilot halfway through an experiment.
PILOT_JAR = Path(os.environ.get("EDH_PILOT_JAR") or FORGE_HOME / "pilot.jar")


def pilot_hooked_methods() -> set[str]:
    """Controller methods PilotController overrides, i.e. decisions that are routed to the pilot."""
    src = (PILOT_SRC / "edh" / "pilot" / "PilotController.java").read_text()
    return set(re.findall(r"@Override\s+public [^(]*?\b(\w+)\(", src))


# Hooks that route decisions made through other controller calls
_ROUTED_VIA = {"getCostDecisionMaker": "sacrifice costs", "orderAndPlaySimultaneousSa": "trigger targets"}


def decision_census(calls: Counter, games: int) -> dict:
    """Per game: how many decisions of each kind Forge made for our seat, split into those the pilot is
    asked about and those it never sees."""
    hooked = pilot_hooked_methods()
    routed, unseen = {}, {}
    for k, v in calls.items():
        (routed if k in hooked else unseen)[k] = round(v / games, 1)
    order = lambda d: dict(sorted(d.items(), key=lambda kv: -kv[1]))
    return {"games": games, "per_game_routed_to_pilot": order(routed), "per_game_never_seen": order(unseen),
            "routed_total_per_game": round(sum(routed.values()), 1),
            "never_seen_total_per_game": round(sum(unseen.values()), 1)}


def build_pilot(force: bool = False) -> Path:
    """Compile the external-pilot plug-in (pilot/src) against the Forge jar."""
    jar = find_jar()
    if not jar:
        raise SystemExit("Forge isn't built. Run `./edh forge setup` first.")
    sources = sorted(PILOT_SRC.rglob("*.java"))
    newest = max(p.stat().st_mtime for p in sources)
    if PILOT_JAR.exists() and not force and PILOT_JAR.stat().st_mtime > max(newest, jar.stat().st_mtime):
        return PILOT_JAR
    build = PILOT_JAR.parent / f"{PILOT_JAR.stem}-build"
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True)
    r = subprocess.run(["javac", "-nowarn", "-cp", str(jar), "-d", str(build), *map(str, sources)],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"pilot build failed:\n{r.stderr[-3000:]}")
    subprocess.run(["jar", "cf", str(PILOT_JAR), "-C", str(build), "."], check=True)
    return PILOT_JAR


# --------------------------------------------------------------------------- card support index

_INDEX_PATH = FORGE_HOME / "forge_cards.json"


def build_card_index(force: bool = False) -> dict[str, dict]:
    """Map of lowercase Forge card name -> {ai_remove_all, ai_remove_random}."""
    if _INDEX_PATH.exists() and not force:
        return json.loads(_INDEX_PATH.read_text())
    folder = res_dir() / "res" / "cardsfolder"
    if not folder.exists():
        return {}
    idx: dict[str, dict] = {}
    for p in folder.rglob("*.txt"):
        try:
            txt = p.read_text(errors="replace")
        except OSError:
            continue
        faces = re.findall(r"^Name:(.+)$", txt, re.M)
        if not faces:
            continue
        flags = {
            "ai_remove_all": "AI:RemoveDeck:All" in txt,
            "ai_remove_random": "AI:RemoveDeck:Random" in txt,
        }
        idx[faces[0].strip().lower()] = flags
        if "AlternateMode:Split" in txt and len(faces) > 1:
            idx[f"{faces[0].strip()} // {faces[1].strip()}".lower()] = flags
    FORGE_HOME.mkdir(parents=True, exist_ok=True)
    _INDEX_PATH.write_text(json.dumps(idx))
    return idx


# Cards Forge's AI never casts in practice even though their scripts carry no AI flag.
# Add to this when a card is in a simmed deck for many games and never appears as cast.
AI_OBSERVED_NEVER_CASTS = {
    "The One Ring": "0 casts in ~120 logged games across 4 decks (Sept 2026)",
}


def support_report(deck: Deck, idx: dict | None = None) -> dict[str, list[str]]:
    idx = idx if idx is not None else build_card_index()
    missing, ai_bad, ai_meh = [], [], []
    for e in deck.commanders + deck.main:
        name = (e.card.forge_name if e.card else e.name)
        info = idx.get(name.lower())
        if info is None:
            missing.append(e.name)
        elif info["ai_remove_all"] or e.name in AI_OBSERVED_NEVER_CASTS:
            ai_bad.append(e.name)
        elif info["ai_remove_random"]:
            ai_meh.append(e.name)
    return {"missing": missing, "ai_cannot_play": ai_bad, "ai_weak": ai_meh}


def forge_deck_text(deck: Deck, label: str, idx: dict, substitute_missing: bool = True) -> tuple[str, list[str]]:
    """Forge .dck text; unsupported cards become basics of the deck's colors (reported back)."""
    subs = []
    colors = [c for c in "WUBRG" if deck.color_identity_mask() & (1 << "WUBRG".index(c))] or ["C"]
    basic = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest", "C": "Wastes"}
    main: list[Entry] = []
    for i, e in enumerate(deck.main):
        name = e.card.forge_name if e.card else e.name
        if name.lower() not in idx and e.name not in BASIC_LANDS:
            if not substitute_missing:
                raise ValueError(f"Forge doesn't support {e.name}")
            subs.append(e.name)
            main.append(Entry(name=basic[colors[i % len(colors)]], qty=e.qty))
        else:
            main.append(Entry(name=name, qty=e.qty, card=e.card))
    d = Deck(commanders=deck.commanders, main=main, title=label)
    return d.to_forge(label), subs


# --------------------------------------------------------------------------- slots

@contextmanager
def forge_slot():
    lockdir = FORGE_HOME / "slots"
    lockdir.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(SLOTS):
            f = open(lockdir / f"slot{i}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                continue
            try:
                yield i
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
            return
        time.sleep(2)


# --------------------------------------------------------------------------- log parsing

_TURN = re.compile(r"^Turn: Turn (\d+) \((Ai\(\d+\)-P\d+)\)")
_CAST = re.compile(r"^Add To Stack: (Ai\(\d+\)-P\d+) cast (.+?)(?: targeting .*)?$")
_LAND = re.compile(r"^Land: (Ai\(\d+\)-P\d+) played (.+?) \(\d+\)$")
_LOST = re.compile(r"^Game Outcome: (Ai\(\d+\)-P\d+) has lost because (.+)$")
_WON = re.compile(r"^Game Outcome: (Ai\(\d+\)-P\d+) has won")
_RESULT = re.compile(r"^Game Result: Game (\d+) ended")
_MULL = re.compile(r"^Mulligan: (Ai\(\d+\)-P\d+) has (kept a hand of (\d+)|mulliganed)")
_LIFE = re.compile(r"^Life: Life: (Ai\(\d+\)-P\d+) (-?\d+) > (-?\d+)")
_PLAYER = re.compile(r"Ai\(\d+\)-(P\d+)")
_NOISE = re.compile(
    r"^(\d\d:\d\d:\d\d \[|Error handling registered|Read cards:|Language '|Upcoming set|The card .* was not assigned"
    r"|Warning: default|Simulation mode|\(ThreadUtil|Picked up JAVA_TOOL_OPTIONS|Ai\(\d+\)-P\d+ vs Ai)"
)


@dataclass
class GameRecord:
    players: list[str]                       # labels P1..Pn in seat order seen
    winner: str | None = None                # label or None (draw / timeout)
    timeout: bool = False
    turns: int = 0
    lost_turn: dict[str, int] = field(default_factory=dict)
    lost_reason: dict[str, str] = field(default_factory=dict)
    casts: dict[str, list[tuple[str, int]]] = field(default_factory=lambda: defaultdict(list))
    lands: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    kept: dict[str, int] = field(default_factory=dict)
    winners: list[str] = field(default_factory=list)
    first_player: str | None = None
    error: str | None = None


def parse_games(output: str) -> list[tuple[GameRecord, list[str]]]:
    games: list[tuple[GameRecord, list[str]]] = []
    cur = GameRecord(players=[])
    lines: list[str] = []
    turn = 0
    timeout_pending = False
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Stopping slow match as draw"):
            timeout_pending = True
            continue
        if "Exception" in line and cur.error is None and not line.startswith(("Add To Stack", "Damage")):
            cur.error = line[:200]
        m = _TURN.match(line)
        if m:
            turn = int(m.group(1))
            lab = _PLAYER.search(m.group(2)).group(1)
            if cur.first_player is None:
                cur.first_player = lab
            if lab not in cur.players:
                cur.players.append(lab)
            lines.append(line)
            continue
        if line.startswith(("Phase:", "Mana:")) or _NOISE.match(line):
            continue
        if line.startswith("Resolve Stack:") and len(line) > 180:
            line = line[:177] + "..."
        lines.append(line)
        m = _CAST.match(line)
        if m:
            cur.casts[_PLAYER.search(m.group(1)).group(1)].append((m.group(2).strip(), turn))
            continue
        m = _LAND.match(line)
        if m:
            cur.lands[_PLAYER.search(m.group(1)).group(1)] += 1
            continue
        m = _MULL.match(line)
        if m and m.group(3):
            cur.kept[_PLAYER.search(m.group(1)).group(1)] = int(m.group(3))
            continue
        m = _LOST.match(line)
        if m:
            lab = _PLAYER.search(m.group(1)).group(1)
            cur.lost_turn[lab] = turn
            cur.lost_reason[lab] = m.group(2)
            continue
        m = _WON.match(line)
        if m:
            cur.winners.append(_PLAYER.search(m.group(1)).group(1))
            cur.winner = cur.winners[-1]
            continue
        m = _RESULT.match(line)
        if m:
            cur.turns = turn
            # Forge sometimes ends a stalled game by declaring *everyone* the winner; that's a draw.
            cur.timeout = timeout_pending or "Draw" in line or len(set(cur.winners)) > 1
            if cur.timeout:
                cur.winner = None
            if turn == 0 and cur.error is None:
                cur.error = "game ended before turn 1 (a controller threw during setup?)"
            games.append((cur, lines))
            cur = GameRecord(players=[])
            lines, turn, timeout_pending = [], 0, False
    return games



_ID_NAME = re.compile(r"([^,]+?) \((\d+)\)")


def graveyard_usage(lines: list[str], us: str, exclude: set[str] = frozenset()) -> dict:
    """Infer spells cast / lands played from our own graveyard in one game.

    Forge logs cards *entering* graveyards (dies, milled, discarded) with ids but
    never logs them leaving, so: track which of our card ids are in the yard, and
    a later cast/land play of that name counts as coming from the graveyard.
    Our ids are the contiguous block Forge assigned to our library.
    """
    me = f"-{us} "
    ids: list[int] = []
    others: list[int] = []
    for ln in lines:
        m = re.match(r"^\w[\w ]*: Ai\(\d+\)-(P\d+) (played|milled|discards|assigned)", ln)
        if m:
            found = [int(i) for _, i in _ID_NAME.findall(ln.split(f"-{m.group(1)} ", 1)[1])]
            (ids if m.group(1) == us else others).extend(found)
    if not ids:
        return {"spells": 0, "lands": 0, "cards": {}}
    # Each player's library gets a contiguous id block; ours runs up to the nearest
    # id seen for any other player (or ~one deck's width if we're at an end).
    lo, hi = min(ids), max(ids)
    below = [i for i in others if i < lo]
    above = [i for i in others if i > hi]
    lo = max(below) + 1 if below else lo - 110
    hi = min(above) - 1 if above else hi + 110
    ours = lambda i: lo <= i <= hi
    yard: dict[int, str] = {}
    spells = lands = 0
    cards: Counter = Counter()
    for ln in lines:
        if " was put into Graveyard from " in ln:
            m = re.match(r"^Zone Change: (.+) \((\d+)\) was put into Graveyard", ln)
            if m and ours(int(m.group(2))) and m.group(1) not in exclude:  # commanders go to the command zone
                yard[int(m.group(2))] = m.group(1)
        elif me in ln and (" milled " in ln or " discards " in ln):
            for nm, i in _ID_NAME.findall(ln.split(" milled " if " milled " in ln else " discards ", 1)[1]):
                nm = nm.strip().removeprefix("and ").strip()
                if ours(int(i)) and nm not in exclude:
                    yard[int(i)] = nm
        elif ln.startswith("Add To Stack:") and f"{me}cast " in ln + " ":
            m = _CAST.match(ln)
            if m:
                nm = m.group(2).strip()
                hit = next((i for i, n in yard.items() if n == nm), None)
                if hit is not None:
                    del yard[hit]
                    spells += 1
                    cards[nm] += 1
        elif ln.startswith("Land:") and me in ln:
            m = re.search(r" played (.+) \((\d+)\)$", ln)
            if m and int(m.group(2)) in yard:
                del yard[int(m.group(2))]
                lands += 1
                cards[m.group(1)] += 1
    return {"spells": spells, "lands": lands, "cards": dict(cards)}


# --------------------------------------------------------------------------- running

def run_pod(deck_texts: list[str], games: int, seed: int, clock: int = 300, pilot_seat: int | None = None,
            sidecar: str | None = None, tag: str = "pod") -> tuple[list[tuple[GameRecord, list[str]]], str]:
    jar = find_jar()
    if not jar:
        raise SystemExit("Forge isn't built. Run `./edh forge setup` (clone + Maven build, ~5-10 min).")
    with forge_slot() as slot:
        home = FORGE_HOME / "slots" / f"home{slot}"
        deckdir = home / ".forge" / "decks" / "commander"
        deckdir.mkdir(parents=True, exist_ok=True)
        for old in deckdir.glob("*.dck"):
            old.unlink()
        names = []
        for i, txt in enumerate(deck_texts):
            fn = f"P{i + 1}.dck"
            (deckdir / fn).write_text(txt)
            names.append(fn)
        if pilot_seat is not None:
            cmd = ["java", f"-Xmx{JAVA_XMX}", f"-Duser.home={home}", "-Djava.awt.headless=true",
                   "-cp", f"{jar}{os.pathsep}{PILOT_JAR}", "edh.pilot.PilotMain",
                   "--pilot-seat", str(pilot_seat), "--sidecar", sidecar or "", "--games", str(games),
                   "--seed", str(seed), "--clock", str(clock), "--tag", tag,
                   *[str(deckdir / n) for n in names]]
        else:
            cmd = ["java", f"-Xmx{JAVA_XMX}", f"-Duser.home={home}", "-Djava.awt.headless=true",
                   "-jar", str(jar), "sim", "-d", *names, "-f", "commander", "-n", str(games),
                   "-s", str(seed), "-c", str(clock)]
        env = dict(os.environ)
        proc = subprocess.run(cmd, cwd=res_dir(), capture_output=True, text=True, env=env,
                              timeout=clock * games + 300)
        out = proc.stdout + "\n" + proc.stderr
    return parse_games(out), out


@dataclass
class SimPlan:
    pods: list[dict]   # {seat_order: [labels], opponents: [paths], seed: int}


def load_gauntlet(bracket: int, pool: Path | None = None) -> list[Path]:
    d = pool or (GAUNTLET / f"b{bracket}")
    decks = sorted(d.glob("*.dck")) + sorted(d.glob("*.txt"))
    if not decks:
        raise SystemExit(f"no gauntlet decks in {d}; run `./edh gauntlet build --bracket {bracket}`")
    return decks


def plan(n_games: int, pod_size: int, games_per_pod: int, opponents: list[Path], seed: int) -> list[dict]:
    rng = random.Random(seed)
    pods = []
    n_pods = max(1, math.ceil(n_games / games_per_pod))
    for i in range(n_pods):
        opp = rng.sample(opponents, k=min(pod_size - 1, len(opponents)))
        seat = rng.randrange(pod_size) if len(opp) == pod_size - 1 else 0
        pods.append({"opponents": [str(p) for p in opp], "seat": seat, "seed": rng.randrange(1, 10**9),
                     "games": min(games_per_pod, n_games - i * games_per_pod)})
    return pods


def _load_any_deck(path: Path, db: CardDB) -> Deck:
    d = Deck.load(path)
    d.resolve(db)  # tolerate unknowns in gauntlet decks; forge_deck_text substitutes them
    return d


def simulate(deck: Deck, opponents: list[Path], db: CardDB, games: int = 40, pod_size: int = 4,
             games_per_pod: int = 5, seed: int = 1, workers: int | None = None, clock: int = 300,
             outdir: Path | None = None, pods: list[dict] | None = None, quiet: bool = False,
             pilot=None, count_decisions: bool = False) -> dict:
    """pilot: an edhkit.pilot.Pilot to fly our seat (None = Forge's own AI).
    count_decisions: with no pilot, run our seat through the pilot plug-in in count-only mode, so Forge
    answers everything but every decision it makes for us is tallied (piloted runs always tally)."""
    idx = build_card_index()
    sidecar = None
    if pilot is not None:
        build_pilot()
        sidecar = pilot.start()
    elif count_decisions:
        build_pilot()
        sidecar = "count"
        clock = max(clock, 900)  # strategist pauses add time; piloted games take ~3-4 min, so 15 min flags a stuck game
    our_text, our_subs = forge_deck_text(deck, "P0", idx)
    pods = pods or plan(games, pod_size, games_per_pod, opponents, seed)
    opp_cache: dict[str, tuple[str, str]] = {}

    def opp_text(path: str) -> str:
        if path not in opp_cache:
            od = _load_any_deck(Path(path), db)
            txt, _ = forge_deck_text(od, "X", idx)
            opp_cache[path] = (txt, od.commanders[0].name if od.commanders else Path(path).stem)
        return opp_cache[path][0]

    for p in pods:  # warm cache serially (DB access isn't thread-safe enough to bother)
        for o in p["opponents"]:
            opp_text(o)

    def run_one(i_pod: tuple[int, dict]):
        i, p = i_pod
        seats: list[tuple[str, str]] = [("opp", o) for o in p["opponents"]]
        seats.insert(p["seat"], ("us", ""))
        texts, labels = [], {}
        for s_i, (kind, path) in enumerate(seats):
            lab = f"P{s_i + 1}"
            txt = our_text if kind == "us" else opp_text(path)
            txt = re.sub(r"^Name=.*$", f"Name={lab}", txt, count=1, flags=re.M)
            texts.append(txt)
            labels[lab] = "US" if kind == "us" else opp_cache[path][1]
        t0 = time.time()
        us_seat = p["seat"] + 1
        results, raw = run_pod(texts, p["games"], p["seed"], clock,
                               pilot_seat=us_seat if sidecar else None, sidecar=sidecar, tag=f"pod{i + 1:02d}")
        if sidecar:
            for m in re.finditer(r"\[pilot\] (?:hook error in ([\w-]+)|(loop breaker))", raw):
                hook_errors[m.group(1) or "loop-breaker"] += 1
            for m in re.finditer(r"\[pilot\] controller-calls \S+ (\{.*\})", raw):
                controller_games[0] += 1
                for k, v in json.loads(m.group(1)).items():
                    controller_calls[k] += v
        if not quiet:
            print(f"  pod {i + 1}/{len(pods)}: {len(results)} games in {time.time() - t0:.0f}s", file=sys.stderr)
        if outdir:
            outdir.mkdir(parents=True, exist_ok=True)
            with open(outdir / f"pod{i + 1:02d}.log", "w") as f:
                f.write(f"# seats: {json.dumps(labels)}\n")
                for g_i, (g, lines) in enumerate(results):
                    f.write(f"\n===== game {g_i + 1} =====\n")
                    f.write("\n".join(lines) + "\n")
            if not results:
                (outdir / f"pod{i + 1:02d}.raw.txt").write_text(raw[-20000:])
        return labels, results

    hook_errors: Counter = Counter()
    controller_calls: Counter = Counter()
    controller_games = [0]
    workers = workers or SLOTS
    with ThreadPoolExecutor(max_workers=workers) as ex:
        outcomes = list(ex.map(run_one, list(enumerate(pods))))
    summary = summarize(deck, outcomes, pod_size)
    if pilot is not None:
        pilot.stop()
        summary["pilot"] = pilot.summary()
        summary["pilot"]["hook_errors_logged"] = dict(hook_errors)  # Java prints the first 3 per hook per JVM
    if controller_games[0]:
        summary["decisions"] = decision_census(controller_calls, controller_games[0])
    summary["substituted_for_forge"] = our_subs
    summary["support"] = support_report(deck, idx)
    summary["pods"] = pods
    if outdir:
        (outdir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


# --------------------------------------------------------------------------- stats

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(deck: Deck, outcomes: list[tuple[dict, list]], pod_size: int) -> dict:
    cmdr_names = {e.card.forge_name if e.card else e.name for e in deck.commanders}
    ours_names = {(e.card.forge_name if e.card else e.name): e.name for e in deck.commanders + deck.main}
    n = wins = timeouts = errors = 0
    rounds_to_win, rounds_lost, game_rounds = [], [], []
    cmd_cast_games, cmd_first_round = 0, []
    card_games: Counter = Counter()
    card_wins: Counter = Counter()
    card_first_round: dict[str, list[int]] = defaultdict(list)
    loss_reasons: Counter = Counter()
    opp_wins: Counter = Counter()
    opp_seen: Counter = Counter()
    gy_spells = gy_lands = 0
    gy_cards: Counter = Counter()
    for labels, results in outcomes:
        us = next(k for k, v in labels.items() if v == "US")
        for g, glines in results:
            gu = graveyard_usage(glines, us, cmdr_names)
            gy_spells += gu["spells"]
            gy_lands += gu["lands"]
            gy_cards.update(gu["cards"])
            n += 1
            errors += bool(g.error)
            r = lambda t: math.ceil(t / pod_size) if t else 0
            game_rounds.append(r(g.turns))
            for lab, name in labels.items():
                if name != "US":
                    opp_seen[name] += 1
                    if g.winner == lab:
                        opp_wins[name] += 1
            if g.timeout:
                timeouts += 1
            won = g.winner == us
            if won:
                wins += 1
                rounds_to_win.append(r(g.turns))
            elif us in g.lost_turn:
                rounds_lost.append(r(g.lost_turn[us]))
                loss_reasons[g.lost_reason.get(us, "?")] += 1
            casts = g.casts.get(us, [])
            seen_this_game = {}
            for name, t in casts:
                if name in ours_names and name not in seen_this_game:
                    seen_this_game[name] = t
            for name, t in seen_this_game.items():
                disp = ours_names[name]
                card_games[disp] += 1
                card_first_round[disp].append(r(t))
                if won:
                    card_wins[disp] += 1
            cmd_turns = [t for nm, t in casts if nm in cmdr_names]
            if cmd_turns:
                cmd_cast_games += 1
                cmd_first_round.append(r(min(cmd_turns)))
    lo, hi = wilson(wins, n)
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    per_card = []
    for e in deck.main:
        if e.card and e.card.is_land:
            continue
        name = e.name
        k = card_games.get(name, 0)
        per_card.append({
            "card": name, "cast_games": k, "cast_rate": round(k / n, 3) if n else 0,
            "win_rate_when_cast": round(card_wins[name] / k, 3) if k else None,
            "avg_first_round": avg(card_first_round.get(name, [])),
        })
    per_card.sort(key=lambda x: (-x["cast_rate"], x["card"]))
    return {
        "games": n, "wins": wins, "win_rate": round(wins / n, 3) if n else 0,
        "win_rate_ci95": [round(lo, 3), round(hi, 3)], "baseline": round(1 / pod_size, 3),
        "timeouts_or_draws": timeouts, "games_with_errors": errors,
        "avg_rounds_per_game": avg(game_rounds), "avg_round_of_our_win": avg(rounds_to_win),
        "avg_round_we_died": avg(rounds_lost), "loss_reasons": dict(loss_reasons),
        "graveyard_spells_per_game": round(gy_spells / n, 2) if n else 0,
        "graveyard_lands_per_game": round(gy_lands / n, 2) if n else 0,
        "graveyard_top": gy_cards.most_common(10),
        "commander_cast_rate": round(cmd_cast_games / n, 3) if n else 0,
        "commander_avg_first_round": avg(cmd_first_round),
        "never_cast": [c["card"] for c in per_card if c["cast_games"] == 0],
        "per_card": per_card,
        "opponents": {k: {"games": opp_seen[k], "wins": opp_wins[k]} for k in opp_seen},
    }


def report(s: dict) -> str:
    L = [f"Forge sim: {s['games']} games, won {s['wins']} ({s['win_rate']:.0%}, 95% CI {s['win_rate_ci95'][0]:.0%}–{s['win_rate_ci95'][1]:.0%}; "
         f"baseline {s['baseline']:.0%}), timeouts/draws {s['timeouts_or_draws']}, errored games {s['games_with_errors']}"]
    L.append(f"  avg game length {s['avg_rounds_per_game']} rounds | we win on round {s['avg_round_of_our_win']} | we die on round {s['avg_round_we_died']}")
    L.append(f"  commander cast in {s['commander_cast_rate']:.0%} of games, first on round {s['commander_avg_first_round']}")
    if "graveyard_spells_per_game" in s:
        L.append(f"  from our graveyard: {s['graveyard_spells_per_game']} spells + {s['graveyard_lands_per_game']} lands per game"
                 + (" (top: " + ", ".join(f"{c} ×{k}" for c, k in s["graveyard_top"][:5]) + ")" if s.get("graveyard_top") else ""))
    if s.get("loss_reasons"):
        L.append("  how we lost: " + ", ".join(f"{k} ×{v}" for k, v in s["loss_reasons"].items()))
    if s.get("pilot"):
        pl = s["pilot"]
        kinds = ", ".join(f"{k} {v['questions']}q/{v['overrules']} overruled" for k, v in sorted(
            pl.get("by_kind", {}).items(), key=lambda kv: -kv[1]["questions"]))
        L.append(f"  pilot: Jev + {pl['strategist']} strategist — {pl['requests']} requests / {pl['questions']} questions, "
                 f"overruled Forge {pl['overrule_rate']:.0%}, latency avg {pl['latency_ms_avg']} ms (p95 {pl['latency_ms_p95']}), "
                 f"Jev ${pl['jev_usd']}" + (f", {pl['strategist_calls']} memos (avg {pl['strategist_ms_avg']} ms), "
                 f"{pl['escalations']} escalations of {pl['escalation_checks']} checks" if pl["strategist_calls"] else ""))
        L.append(f"    by kind: {kinds}")
        if pl.get("strategist_errors"):
            L.append(f"    STRATEGIST FAILED {pl['strategist_errors']} of {pl['strategist_calls']} times (previous memo kept): "
                     "these games don't fully reflect the strategist. See memo_error records in pilot_decisions.jsonl.")
        if pl.get("hook_errors_logged"):
            L.append("    HOOK ERRORS (fell back to Forge): " + ", ".join(f"{k} ×{v}" for k, v in pl["hook_errors_logged"].items()))
    if s.get("decisions"):
        dc = s["decisions"]
        L.append(f"  decisions per game for our seat: {dc['routed_total_per_game']} controller calls routed to the pilot, "
                 f"{dc['never_seen_total_per_game']} never seen: "
                 + ", ".join(f"{k} {v}" for k, v in list(dc["per_game_never_seen"].items())[:10]))
    sup = s.get("support", {})
    if sup.get("missing"):
        L.append(f"  NOT IN FORGE (replaced by basics for the sim): {', '.join(sup['missing'])}")
    if sup.get("ai_cannot_play"):
        L.append(f"  Forge AI flags as unplayable for AI (sim undervalues these): {', '.join(sup['ai_cannot_play'])}")
    top = [c for c in s["per_card"] if c["cast_games"]][:12]
    if top:
        L.append("  most-cast spells: " + "; ".join(f"{c['card']} {c['cast_rate']:.0%}" for c in top))
    if s["never_cast"]:
        L.append(f"  never cast ({len(s['never_cast'])}): {', '.join(s['never_cast'][:30])}")
    opp = sorted(s.get("opponents", {}).items(), key=lambda kv: -kv[1]["wins"] / max(kv[1]["games"], 1))
    if opp:
        L.append("  opponents (wins/games): " + "; ".join(f"{k} {v['wins']}/{v['games']}" for k, v in opp))
    return "\n".join(L)


def compare(deck_a: Deck, deck_b: Deck, opponents: list[Path], db: CardDB, **kw) -> dict:
    """Paired comparison: identical pods, seats and seeds for both decks (common random numbers)."""
    kw = dict(kw)
    outdir = kw.pop("outdir", None)
    pods = plan(kw.pop("games", 40), kw.get("pod_size", 4), kw.pop("games_per_pod", 5), opponents, kw.pop("seed", 1))
    sa = simulate(deck_a, opponents, db, pods=pods, outdir=(outdir / "A") if outdir else None, **kw)
    sb = simulate(deck_b, opponents, db, pods=pods, outdir=(outdir / "B") if outdir else None, **kw)
    diff = sb["win_rate"] - sa["win_rate"]
    n = min(sa["games"], sb["games"])
    se = math.sqrt(max(sa["win_rate"] * (1 - sa["win_rate"]) + sb["win_rate"] * (1 - sb["win_rate"]), 1e-9) / max(n, 1))
    return {"A": sa, "B": sb, "delta_win_rate": round(diff, 3), "approx_se": round(se, 3),
            "verdict": ("B better" if diff > 2 * se else "A better" if diff < -2 * se else "no clear difference")}
