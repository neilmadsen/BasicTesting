"""Critical-state scenarios: replay the moment a game turned, many times, instead of playing many games.

    ./edh critical <sim-out> <game> <turn> --deck deck.txt [--seeds 4] [--turns 4] [--strategist claude-cli]
                   [--hand-swap "Old=New"] [--variant-deck new.txt]

Takes our first main-phase decision on `turn` from a --log-state pilot log and rebuilds that board as a Forge
puzzle (edhkit/scenario.py): every battlefield with counters, tapped and summoning-sick status, attachments and
tokens, our hand and graveyard, life totals, and commanders in the command zone. What the log can't know is
sampled per seed from the decklists: opponents' hands and graveyards (at their logged sizes) and every library.
Our seat is played by the pilot (a fresh sidecar per run), the others by Forge's AI, for `--turns` turns.

Each run reports whether we're alive, our life, and who lost. Comparing pilot or deck variants over the same
seeds on the same boards gives a paired signal from a handful of runs, where whole games need hundreds: the board
that decided a lost game is fixed, so the noise of the opening and midgame is gone.

Known gaps: commander tax isn't settable in a puzzle (recasts look cheaper than they were); tokens are matched to
Forge token scripts by name, type and size, so a token's keywords can differ; "until end of turn" effects and
damage marked earlier in the turn aren't carried.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from .cards import CardDB
from .deck import Deck
from .paths import GAUNTLET

ENTRY = re.compile(r"^(?P<name>.+?)(?: (?P<p>-?\d+)/(?P<t>-?\d+))?(?P<rest>(?: \[[^\]]*\]| \{[^}]*\}| x\d+| \(tapped \d+\))*)$")
COUNTERS = re.compile(r"\[([A-Z0-9_]+)(?: x(\d+))?\]")
LIFE = re.compile(r"^Life: Life: Ai\(\d+\)-(P\d+) (-?\d+) > (-?\d+)")
LOST = re.compile(r"Ai\(\d+\)-(P\d+) (?:has lost|lost the game)")


def _token_dir() -> Path:
    from . import forge
    res = Path(forge.res_dir())
    return res / "tokenscripts" if (res / "tokenscripts").exists() else res / "res" / "tokenscripts"


def token_script(name: str, power: int | None, tough: int | None, scripts: list[str]) -> str | None:
    """Best Forge token script for a logged token ("Angel Token 4/4"): same size and creature type."""
    words = [w.lower() for w in re.sub(r"\bToken\b", "", name).split() if w.isalpha()]
    if power is None or not words:
        return None
    pat = re.compile(rf"^[a-z]+_{power}_{tough}_(?:[a-z]+_)*{words[-1]}(?:_|$)")
    hits = sorted((s for s in scripts if pat.match(s)), key=lambda s: (s.count("_"), s))
    if not hits:
        # the logged size includes anthems and lords (Edgar's 1/1 Vampires showed as 3/3 and 4/4): fall back to the
        # smallest token of that creature type, which is what the anthem was pumping
        any_size = re.compile(rf"^[a-z]+_(\d+)_(\d+)_(?:[a-z]+_)*{words[-1]}(?:_|$)")
        sized = [(int(m.group(1)) + int(m.group(2)), s.count("_"), s) for s in scripts if (m := any_size.match(s))]
        hits = [s for *_, s in sorted(sized)]
    if not hits:
        return None
    flyer = [h for h in hits if "flying" in h]  # angels, spirits, thopters, birds are almost always fliers
    return (flyer[0] if words[-1] in {"angel", "spirit", "thopter", "bird", "faerie", "dragon", "bat"} and flyer
            else hits[0])


def parse_board_entry(entry: str) -> dict:
    m = ENTRY.match(entry.strip())
    if not m:
        return {"name": entry, "n": 1}
    rest = m["rest"] or ""
    counters = {}
    for block in re.findall(r"\{([^}]*)\}", rest):
        for c, k in COUNTERS.findall(block):
            counters[c] = int(k or 1)
    wearing = re.search(r"\[wearing ([^\]]+)\]", rest)
    tapped = re.search(r"\(tapped (\d+)\)", rest)
    n = re.search(r" x(\d+)", rest)
    return {"name": m["name"].strip(), "n": int(n.group(1)) if n else 1,
            "p": int(m["p"]) if m["p"] else None, "t": int(m["t"]) if m["t"] else None,
            "land": "[land]" in rest, "token": "[token]" in rest, "sick": "[summoning sick]" in rest,
            "tapped": int(tapped.group(1)) if tapped else 0, "counters": counters,
            "wearing": [w.strip() for w in wearing.group(1).split(",")] if wearing else []}


def _players(state: dict) -> list[dict]:
    import ast
    p = state.get("players")
    return ast.literal_eval(p) if isinstance(p, str) else (p or [])


def load_state(sim: Path, game: str, turn: int) -> tuple[dict, str]:
    """Our first main-phase-1 decision on `turn` (else our first decision that turn), and the memo then in force."""
    memo, first, chosen = "", None, None
    for line in (sim / "pilot_decisions.jsonl").open():
        r = json.loads(line)
        if r.get("game") != game:
            continue
        if r.get("type") == "memo" and (r.get("turn") or 0) <= turn:
            memo = r.get("memo", "")
        if r.get("type") == "decision" and "state" in r and (r.get("turn") or 0) == turn:
            st = r["state"]
            if st.get("active") != st.get("me"):
                continue
            first = first or st
            if r.get("phase") == "MAIN1":
                chosen = st
                break
    st = chosen or first
    if st is None:
        raise SystemExit(f"no decision of ours on turn {turn} in {game}")
    st = dict(st)
    st["players"] = _players(st)
    return st, memo


def gauntlet_by_commander(bracket: int = 3) -> dict[str, Path]:
    out = {}
    for p in sorted((GAUNTLET / f"b{bracket}").glob("*.dck")):
        lines = p.read_text().splitlines()
        if "[Commander]" in lines:
            i = lines.index("[Commander]")
            for ln in lines[i + 1:]:
                if ln.startswith("["):
                    break
                m = re.match(r"\d+\s+(.+?)(?:\|.*)?$", ln.strip())
                if m:
                    out[m.group(1)] = p
    return out


@dataclass
class Puzzle:
    text: str
    decks: list[Path]          # seat order: ours first
    notes: list[str]


def _deck_names(deck: Deck) -> list[str]:
    out = []
    for e in deck.main:
        out += [e.name] * e.qty
    return out


def build(state: dict, our_deck: Path, seed: int, db: CardDB, bracket: int = 3,
          hand_swap: dict[str, str] | None = None) -> Puzzle:
    rng = random.Random(seed)
    players = state["players"]
    me_i = next(i for i, p in enumerate(players) if p.get("is_me"))
    order = players[me_i:] + players[:me_i]             # p0 = us, then turn order
    seat = {p["name"]: f"p{i}" for i, p in enumerate(order)}
    by_cmd = gauntlet_by_commander(bracket)
    scripts = sorted(f[:-4] for f in __import__("os").listdir(_token_dir()) if f.endswith(".txt"))
    notes, decks, lines = [], [our_deck], []
    lines += [f"turn={state.get('turn', 1)}", f"activeplayer={seat.get(state.get('active'), 'p0')}",
              "activephase=MAIN1", "removesummoningsickness=false"]
    next_id = [1]

    def nid() -> int:
        next_id[0] += 1
        return next_id[0]

    for p in order:
        sx = seat[p["name"]]
        is_me = p.get("is_me")
        lines.append(f"{sx}life={p.get('life', 40)}")
        if p.get("poison"):
            lines.append(f"{sx}counters=POISON={p['poison']}")
        if is_me:
            deck = Deck.load(our_deck)
        else:
            cmd = (p.get("commanders") or [None])[0]
            path = by_cmd.get(cmd)
            if not path:
                raise SystemExit(f"no gauntlet deck for {cmd}")
            decks.append(path)
            deck = Deck.load(path)
        commanders = [e.name for e in deck.commanders]
        # battlefield
        bf, known, ids, attach = [], [], {}, []
        for raw in p.get("battlefield", []):
            e = parse_board_entry(raw)
            card = None
            try:
                card = db.require(e["name"])
            except KeyError:
                pass
            for k in range(e["n"]):
                cid = nid()
                bits = []
                if e["token"] and card is None:
                    base_p = (e["p"] - e["counters"].get("P1P1", 0) + e["counters"].get("M1M1", 0)) if e["p"] is not None else None
                    base_t = (e["t"] - e["counters"].get("P1P1", 0) + e["counters"].get("M1M1", 0)) if e["t"] is not None else None
                    ts = token_script(e["name"], base_p, base_t, scripts)
                    if not ts:
                        notes.append(f"{p['name']}: no token script for {raw!r}; left out")
                        break
                    bits.append(f"T:{ts}")  # T: is a token script name; t: is an inline token spec
                else:
                    if card is None:
                        notes.append(f"{p['name']}: unknown card {e['name']!r}; left out")
                        break
                    bits.append(card.name)
                    if e["token"]:
                        bits.append("IsToken")
                    else:
                        known.append(card.name)
                    if card.name in commanders:
                        bits.append("IsCommander")
                bits.append(f"Id:{cid}")
                if k < e["tapped"]:
                    bits.append("Tapped")
                if e["sick"]:
                    bits.append("SummonSick")
                if e["counters"]:
                    bits.append("Counters:" + ",".join(f"{c}={v}" for c, v in e["counters"].items()))
                ids.setdefault(e["name"], []).append(cid)
                for w in e["wearing"]:
                    attach.append((w, cid))
                bf.append(bits)
        for host_name_worn, host_id in attach:      # equipment/auras named in "[wearing X]" attach to that host
            for bits in bf:
                if bits[0] == host_name_worn and not any(b.startswith("AttachedTo:") for b in bits):
                    bits.append(f"AttachedTo:{host_id}")
                    break
        lines.append(f"{sx}battlefield=" + ";".join("|".join(b) for b in bf))
        # command zone: commanders not on the battlefield
        on_bf = {b[0] for b in bf}
        cz = [c for c in commanders if c not in on_bf]
        if cz:
            lines.append(f"{sx}command=" + ";".join(f"{c}|IsCommander" for c in cz))
        pool = _deck_names(deck)
        for name in known:
            if name in pool:
                pool.remove(name)
        if is_me:
            hand = list(state.get("my_hand", []))
            for old, new in (hand_swap or {}).items():
                if old in hand:
                    hand[hand.index(old)] = new
                    if new in pool:
                        pool.remove(new)
                    notes.append(f"hand: {old} -> {new}")
            grave = list(state.get("my_graveyard", []))
            for name in hand + grave:
                if name in pool:
                    pool.remove(name)
        else:
            rng.shuffle(pool)
            hand = [pool.pop() for _ in range(min(p.get("hand_size", 0), len(pool)))]
            grave = [pool.pop() for _ in range(min(p.get("graveyard_size", 0), len(pool)))]
        rng.shuffle(pool)
        lib = pool[:max(0, p.get("library_size", len(pool)))]
        lines.append(f"{sx}hand=" + ";".join(hand))
        lines.append(f"{sx}graveyard=" + ";".join(grave))
        lines.append(f"{sx}library=" + ";".join(lib))
    return Puzzle("\n".join(lines) + "\n", decks, notes)


def outcome(lines: list[str], state: dict) -> dict:
    """Final life per player and who lost, from the scenario's game log, in original seat names."""
    players = state["players"]
    me_i = next(i for i, p in enumerate(players) if p.get("is_me"))
    order = players[me_i:] + players[:me_i]
    to_orig = {f"P{i + 1}": p["name"] for i, p in enumerate(order)}   # scenario seats are P1.. in our order
    life = {p["name"]: p.get("life", 40) for p in players}
    lost = set()
    for ln in lines:
        if m := LIFE.match(ln):
            life[to_orig.get(m.group(1), m.group(1))] = int(m.group(3))
        for m in LOST.finditer(ln):
            lost.add(to_orig.get(m.group(1), m.group(1)))
    me = players[me_i]["name"]
    for n, v in life.items():
        if v <= 0:
            lost.add(n)
    return {"alive": me not in lost, "our_life": life[me], "life": life, "lost": sorted(lost)}


def run(sim: Path, game: str, turn: int, deck: Path, seeds: list[int], turns: int = 4,
        strategist: str = "claude-cli", hand_swap: dict[str, str] | None = None, out_dir: Path | None = None,
        bracket: int = 3, puzzle_only: bool = False, timeout: int = 2400) -> list[dict]:
    from . import pilot as P
    from . import scenario
    db = CardDB()
    state, memo = load_state(sim, game, turn)
    results = []
    for seed in seeds:
        pz = build(state, deck, seed, db, bracket, hand_swap)
        if puzzle_only:
            results.append({"seed": seed, "puzzle": pz.text, "notes": pz.notes})
            continue
        folder = deck.resolve().parent
        log_dir = (out_dir or Path("/tmp")) / f"{game}-t{turn}-s{seed}"
        log_dir.mkdir(parents=True, exist_ok=True)
        pilot = P.Pilot(P.deck_plan(folder / "brief.md", folder / "notes.md"), strategist=strategist,
                        log_dir=log_dir, log_state=True, version="v3", deck_path=deck, every=1)
        url = pilot.start()
        try:
            lines = scenario.run(pz.text, deck, players=len(pz.decks), turns=turns, seed=seed, pilot_seat=1,
                                 sidecar=url, opponents=pz.decks[1:], timeout=timeout)
        finally:
            pilot.stop()
        (log_dir / "game.log").write_text("\n".join(lines))
        (log_dir / "puzzle.txt").write_text(pz.text)
        turns_seen = sum(1 for ln in lines if ln.startswith("Turn: Turn "))
        res = {"seed": seed, **outcome(lines, state), "turns_played": max(0, turns_seen - 1), "notes": pz.notes,
               "log": str(log_dir)}
        if res["turns_played"] < turns - 1:
            res["notes"] = res["notes"] + [f"only {res['turns_played']} of {turns} turns played (clock or crash)"]
        results.append(res)
    return results
