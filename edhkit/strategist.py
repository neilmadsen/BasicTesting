"""Strategist v3: what a strong player knows when planning a turn, and a memo that says it.

The v2 strategist saw the design brief, a board of card names, and an unreliable
mana estimate. An expert review of its memos (see research/) found its biggest
gaps were a missing win path, unbudgeted answers, mana and rules arithmetic, and
information it simply didn't have: the real decklist, card text and costs, what
opposing commanders do, and game facts such as commander tax. v3 supplies:

- our deck by zone, with the builder's role notes; the library is what's left to tutor;
- full oracle text with mana costs for everything relevant in view (card DB, else Forge);
- opponent dossiers (gauntlet/dossiers/, see dossier.py);
- our untapped mana sources counted from oracle text, not Forge's estimate;
- game facts the Java side reports when available (commander tax, stolen
  permanents, monarch, recent casts);
- a memo format with a mandatory win path and answer earmarks, and a pre-memo checklist.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import dossier as dossiers
from .cards import CardDB
from .deck import Deck
from .pilot import feed_hazards, parse_entry

SYSTEM = (
    "You are the strategist for our seat in a four-player Commander game. A fast executor model makes every "
    "decision (casts, attacks, blocks, targets, sacrifices) and reads your memo before each one. It cannot do "
    "multi-turn arithmetic and remembers nothing but your memo, so the memo must carry the plan.\n\n"
    "Before writing, check silently:\n"
    "1. Lethal both ways: can any opponent kill us before our next turn (evasive and unblockable power, "
    "drains, commander damage, poison, what their dossier says they do)? Can we kill anyone this turn or next?\n"
    "2. Mana: use the counted untapped sources and commander tax you are given; fit this turn's plays to "
    "that exact number, using the costs in the card text.\n"
    "3. Rules: check every card's actual text and cost. Abilities granted by a permanent (e.g. playing cards "
    "from a graveyard) exist only while it is on the battlefield. Check colour and type restrictions on our "
    "removal against each target (e.g. 'nonblack').\n"
    "4. Threats by trajectory, judged from this board: who wins soonest if unchecked, counting the engines "
    "actually on the battlefield and emblems in the command zone, not cards a dossier says the deck might run. "
    "What our own plays feed: death triggers (each creature we kill or sacrifice may drain us or grow theirs), "
    "cast triggers. A commander we kill returns from the command zone for 2 more mana, so killing it buys a turn "
    "or two; spend premium removal on it only when it is what is winning.\n"
    "4b. Rank the opponents themselves, not just their cards: who most endangers our winning. The biggest board "
    "is not always first: a combo deck with cards in hand and open mana, a control deck's inevitability, a drain "
    "engine, or commander damage on us can outrank it (use OPPONENT STANDING and the dossiers). A low life total "
    "is a reason to attack someone only if we can finish them.\n"
    "5. Answers: list our answers in hand, recursive in the graveyard and still tutorable; earmark each.\n"
    "6. Windows and exposure: which opponents are tapped out or holding mana and cards; given each one's "
    "INTERACTION profile (expected wipes, counters, graveyard hate), what we lose if they have it. Commit "
    "only what advances the target, keep the rest back, and don't walk key pieces into open counter mana "
    "or a likely wipe without a reason.\n"
    "7. Target state and win path: the board where our deck is winning, what's missing (name tutor targets "
    "in our library), and how and when we close.\n\n"
    "Write at most 260 words, plain text, seven labelled lines:\n"
    "THIS TURN: ordered plays with their mana, including instant-speed plans for opponents' turns.\n"
    "TARGET: the board we are building toward over 2-3 turns and the missing pieces (by name).\n"
    "WIN PATH: how we close, with which cards, and our rough clock against the fastest opponent's.\n"
    "THREAT ORDER: the opponents ranked, written first as e.g. 'P3 > P1 > P2', then one short clause each: why "
    "(board, combo, control, drain, commander damage) and our stance (attack them, remove X, hold a counter for "
    "Y, leave them alone for now). The executor aims attacks and removal by this order.\n"
    "THREATS & ANSWERS: ranked threats, each with the specific answer earmarked; what not to feed.\n"
    "HOLD: specific cards or mana to keep back and what for, including what we deliberately don't commit "
    "into a likely wipe or counter (never land drops or free plays without a concrete reason).\n"
    "REPLAN IF: specific events that would make this plan wrong."
)


MULTI_TURN = (
    "\n\nThis memo has to carry the executor for {k} of our turns: the next re-plan is scheduled {k} turns from now "
    "(a board shock, such as a wipe or our commander dying, triggers one sooner). So add a seventh line right after "
    "THIS TURN:\n"
    "NEXT TURNS: for each of our following {k1} turns, the plays in priority order with the mana each needs, "
    "conditional where the board or our draws decide (\"if Muldrotha is on the battlefield: ...; otherwise ...\"). "
    "The executor follows NEXT TURNS once THIS TURN is over, so name the cards. You may use up to {words} words."
)


def system_for(horizon: int = 1) -> str:
    """The strategist's system prompt for a memo that must last `horizon` of our turns."""
    if horizon <= 1:
        return SYSTEM
    return SYSTEM + MULTI_TURN.format(k=horizon, k1=horizon - 1, words=230 + 60 * (horizon - 1))


def verify_system(horizon: int = 1) -> str:
    return system_for(horizon) + (
        "\n\nYou are now checking a draft memo for this position before the executor sees it. Go through it "
        "line by line: add up the mana of THIS TURN against the counted sources and commander tax; check every card's "
        "cost, text, timing and targeting restrictions (colour, type, indestructible, ward) and every rules claim "
        "(e.g. graveyard permissions only while their source is on the battlefield, one permanent per type per turn); "
        "check the lethal math both ways. Fix every error and output ONLY the corrected memo in the same format.")


VERIFY_SYSTEM = verify_system(1)


def verify_prompt(prompt_text: str, draft: str) -> str:
    """A second pass that audits a draft memo. In blind A/B on 20 boards the checked memo beat the draft
    17-2 (research/2026-09-23-strategist-memos.md): a separate checking step catches mana, lane and
    rules errors that a single pass at higher effort does not."""
    return f"{prompt_text}\n\nDRAFT MEMO TO CHECK:\n{draft}"


# --------------------------------------------------------------------------- pieces

def _role(note: str) -> str:
    head = note.split(":", 1)[0].strip()
    return re.sub(r"^GEM\s+", "", head)[:40] or "other"


def _names_on(board: list[str]) -> Counter:
    c = Counter()
    for entry in board:
        e = parse_entry(entry)
        c[e["name"]] += e["n"]
    return c


def _me(state: dict) -> dict:
    return next((p for p in state.get("players", []) if p.get("is_me")), {})


def deck_view(deck: Deck, state: dict, db: CardDB | None = None) -> str:
    notes = {e.name: e.note for e in deck.commanders + deck.main}
    front = {n.split(" // ")[0]: n for n in notes}  # Forge shows DFCs by their front name
    def key(name: str) -> str:
        return name if name in notes else front.get(name, name)
    hand = [key(n) for n in state.get("my_hand", [])]
    grave = [key(n) for n in state.get("my_graveyard", [])]
    bf = _names_on(_me(state).get("battlefield", []))
    command = [key(n) for n in state.get("my_command_zone", []) if key(n) in notes]
    seen = Counter(hand) + Counter(grave) + Counter({key(n): k for n, k in bf.items()}) + Counter(command)
    library = []
    for e in deck.commanders + deck.main:
        left = e.qty - seen.get(e.name, 0)
        if left > 0 and e not in deck.commanders:
            library.append((e.name, left, e.note))

    def line(n: str) -> str:
        return f"- {n}: {notes.get(n, '')[:150]}" if notes.get(n) else f"- {n}"
    out = ["OUR DECK (the builder's notes say what each card is for)"]
    for title, names in (("Hand", hand), ("Graveyard", grave), ("Command zone", command),
                         ("Battlefield (ours)", [key(n) for n in bf])):
        if names:
            out.append(f"{title}:\n" + "\n".join(line(n) for n in dict.fromkeys(names)))
    by_role: dict[str, list[str]] = {}
    for name, qty, note in library:
        card = db.get(name) if db else None
        role = _role(note) if note else ("lands" if card and card.is_land else "other")
        by_role.setdefault(role, []).append(name + (f" ×{qty}" if qty > 1 else ""))
    out.append(f"Still in library ({sum(q for _, q, _ in library)} cards; tutorable, order unknown):")
    out += [f"- {role}: {', '.join(names)}" for role, names in sorted(by_role.items(), key=lambda kv: -len(kv[1]))]
    return "\n".join(out)


def card_texts(state: dict, db: CardDB) -> str:
    """Full oracle text and cost for what matters now; Forge's text for tokens and unknowns."""
    names: list[str] = []
    names += state.get("my_hand", []) + state.get("my_graveyard", [])
    for p in state.get("players", []):
        names += p.get("commanders") or []
        for entry in p.get("battlefield", []):
            e = parse_entry(entry)
            if not e["land"]:
                names.append(e["name"])
    forge_text = state.get("card_text", {})
    names += list(forge_text)  # includes spells on the stack, whose one-line descriptions get clipped
    ours = _me(state).get("battlefield", [])
    our_lands = {parse_entry(e)["name"] for e in ours if parse_entry(e)["land"]}
    our_lands |= set(state.get("my_hand", [])) | set(state.get("my_graveyard", []))
    lines = []
    for name in dict.fromkeys(names + sorted(our_lands)):
        c = db.get(name)
        if c and c.is_land and name in our_lands and "Basic" not in c.type_line and len(c.text) > 40:
            lines.append(f"- {c.name} | {c.type_line} | {c.text.replace(chr(10), ' ')[:400]}")
        elif c and not c.is_land:
            pt = f" {c.pt}" if c.pt else ""
            lines.append(f"- {c.name} {c.mana_cost} | {c.type_line}{pt} | {c.text.replace(chr(10), ' ')[:700]}")
        elif not c and name in forge_text:
            lines.append(f"- {name} | {forge_text[name]}")
    return "CARD TEXT (oracle, with mana costs):\n" + "\n".join(lines)


_ADD = re.compile(r"Add ((?:\{[^}]+\})+)(,? or |, )?")


def _mana_from(card) -> int:
    """How much mana one activation of this permanent makes (0 if it isn't a mana source)."""
    if not card:
        return 0
    m = _ADD.search(card.text)
    if not m:
        return 1 if "mana of any" in card.text and "Add" in card.text else 0
    if m.group(2):          # "Add {B}, {G}, or {U}" / "Add {B} or {G}": one of them
        return 1
    return len(re.findall(r"\{[^}]+\}", m.group(1)))


def mana_view(state: dict, db: CardDB) -> str:
    me = _me(state)
    total, srcs, lands, untapped_lands = 0, [], 0, 0
    for entry in me.get("battlefield", []):
        e = parse_entry(entry)
        tapped = int(re.search(r"\(tapped (\d+)\)", entry).group(1)) if "(tapped" in entry else 0
        free = e["n"] - tapped
        card = db.get(e["name"])
        if e["land"]:
            lands += e["n"]
            untapped_lands += max(0, free)
        each = _mana_from(card)
        if each and free > 0:
            total += each * free
            srcs.append(f"{e['name']}" + (f" ×{free}" if free > 1 else "") + (f" ({each} each)" if each > 1 else ""))
    facts = [f"MANA: {total} from untapped sources now: {', '.join(srcs) or 'none'}. "
             f"Lands on battlefield {lands} ({untapped_lands} untapped); fetch lands make no mana themselves."]
    tax = state.get("commander_tax")
    if tax:
        facts.append("Commander tax (extra generic mana to cast from the command zone): "
                     + ", ".join(f"{k} +{v}" for k, v in tax.items()))
    active = state.get("active")
    facts.append(f"It is {'our' if active == state.get('me') else active + chr(39) + 's'} turn ({state.get('phase')}). "
                 f"Turn order: {', '.join(p['name'] for p in state.get('players', []))}.")
    return "\n".join(facts)


def opponents_view(state: dict) -> str:
    out = ["OPPONENTS (dossiers describe each commander's typical deck, not this exact list):"]
    for p in state.get("players", []):
        if p.get("is_me") or p.get("lost"):
            continue
        cmdrs = p.get("commanders") or []
        out.append(f"{p['name']} ({', '.join(cmdrs)}), life {p.get('life')}, hand {p.get('hand_size')}, "
                   f"graveyard {p.get('graveyard_size')}:")
        for c in cmdrs:
            d = dossiers.get(c)
            out.append(d if d else "(no dossier)")
    return "\n".join(out)


_PT = re.compile(r" (\d+)/(\d+)")
_X = re.compile(r" x(\d+)")
_TAPPED = re.compile(r"\(tapped (\d+)\)")


def opponent_standing(state: dict) -> str:
    """Per-opponent facts for ranking threats: board, mana, cards, clock. Evidence, not a verdict: a combo or
    control player can be the top threat with little of this showing."""
    me = _me(state)
    lives = {p["name"]: p.get("life", 0) for p in state.get("players", []) if not p.get("lost")}
    casts = {}
    for line in state.get("recent_casts", []):
        m = re.match(r"(P\d) (?:cast|activated) (.+?)(?: targeting|\(|$)", line)
        if m:
            casts.setdefault(m.group(1), []).append(m.group(2).strip())
    out = ["OPPONENT STANDING (facts from the board, not a ranking):"]
    for p in state.get("players", []):
        if p.get("is_me") or p.get("lost"):
            continue
        power = creatures = other = lands = untapped = 0
        for e in p.get("battlefield", []):
            n = int(_X.search(e).group(1)) if _X.search(e) else 1
            tapped = int(_TAPPED.search(e).group(1)) if _TAPPED.search(e) else 0
            if "[land]" in e:
                lands += n
                untapped += n - tapped
            elif _PT.search(e):
                creatures += n
                power += int(_PT.search(e).group(1)) * n
            else:
                other += n
        kills = [q for q, life in lives.items() if q != p["name"] and 0 < life <= power]
        who = ["us" if q == me.get("name") else q for q in kills]
        bits = [f"life {p.get('life')}" + (f", poison {p['poison']}" if p.get("poison") else ""),
                f"{creatures} creatures with {power} power" + (f" (enough to kill {', '.join(who)} if unblocked)" if who else ""),
                f"{other} other nonland permanents", f"{lands} lands ({untapped} untapped)",
                f"hand {p.get('hand_size')}", f"graveyard {p.get('graveyard_size')}", f"library {p.get('library_size')}"]
        fx = [e for e in p.get("command_zone_effects", []) if e != "Commander Effect"]
        if fx:
            bits.append("emblems/effects: " + "; ".join(fx))
        if casts.get(p["name"]):
            bits.append("recently cast: " + ", ".join(casts[p["name"]][-4:]))
        out.append(f"- {p['name']} ({', '.join(p.get('commanders') or [])}): " + "; ".join(bits))
    return "\n".join(out)


def game_facts(state: dict) -> str:
    facts = []
    if state.get("stolen"):
        facts.append("Controlled by someone other than the owner: " + "; ".join(state["stolen"]))
    if state.get("monarch"):
        facts.append(f"Monarch: {state['monarch']}")
    for pl in state.get("players", []):
        fx = [e for e in pl.get("command_zone_effects", []) if e != "Commander Effect"]
        if fx and not pl.get("lost"):
            who = "we have" if pl.get("is_me") else f"{pl['name']} has"
            facts.append(f"Emblems and lasting effects {who} (text under CARD TEXT): " + "; ".join(fx))
    hazards = feed_hazards(state)
    if hazards:
        facts.append("Opponents' triggers our own plays feed: " + "; ".join(hazards))
    if state.get("recent_casts"):
        facts.append("Recent casts and activations, oldest first:\n" + "\n".join(f"- {x}" for x in state["recent_casts"]))
    return ("GAME FACTS\n" + "\n".join(facts)) if facts else ""


def board_json(state: dict) -> str:
    drop = {"card_text", "my_mana_available", "commander_tax", "stolen", "monarch", "recent_casts"}
    return json.dumps({k: v for k, v in state.items() if k not in drop}, ensure_ascii=False)


def prompt(plan: str, deck: Deck, db: CardDB, state: dict, previous_memo: str, reason: str) -> str:
    parts = [f"DECK PLAN (design brief and pilot notes):\n{plan}", deck_view(deck, state, db), opponents_view(state),
             opponent_standing(state),
             mana_view(state, db), game_facts(state), card_texts(state, db),
             f"BOARD (JSON):\n{board_json(state)}", f"PREVIOUS MEMO:\n{previous_memo or '(none)'}",
             f"REASON FOR THIS MEMO: {reason}", "Write the new memo."]
    return "\n\n".join(p for p in parts if p)
