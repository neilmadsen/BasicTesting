"""Two-layer pilot for Forge games: an LLM strategist and a Jev executor.

The Java plug-in (pilot/src/edh/pilot) routes most of our seat's decisions here
over localhost HTTP (POST /ask). Each request is one decision *kind* (action,
attack, block, mulligan, confirm, choose, sacrifice, surveil/scry, trigger target,
sacrifice cost) with one or more choice questions, each carrying Forge's own
answer as the default.

  strategist (slow): an LLM writes a short memo (PRIORITIES / THREAT / HOLD /
      REPLAN IF) at the start of each of our turns, and again whenever the
      executor escalates. The game pauses for it by default.
  executor (fast, every decision): Jev answers every question of a request in
      one call (speculative fan-out). It overrules Forge only when its choice
      beats Forge's by a probability margin.
  escalation: code diffs the board against the one the memo was written for.
      When something notable changed (big permanent losses, life swings, our
      commander leaving, a player dying), Jev also answers "is the memo now
      wrong?" A yes triggers an immediate re-plan, then the decision is re-asked
      under the new memo.

Strategist providers: static (no LLM) | claude-cli (headless `claude -p`,
session login) | anthropic (Anthropic Python SDK, needs credentials).
"""

from __future__ import annotations

import functools
import json
import os
import re
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

from . import claude_cli, jev

STRATEGIST_MODEL = os.environ.get("EDH_STRATEGIST_MODEL", "claude-opus-5-5")
# Overrule Forge's own answer only when Jev's choice beats it by this probability margin.
# Jev overrules Forge only when its choice leads Forge's answer by this probability margin. A blind audit of
# the decisions gated at 0.15 found Jev's sub-margin preferences a coin flip overall (55-53), worse than
# Forge's below a 0.10 lead (24-33) and better between 0.10 and 0.15 (21-13), so the gate is 0.10.
CONFIDENCE_GATE = float(os.environ.get("EDH_PILOT_GATE", "0.10"))
# Vetoing a play Forge's AI wants to make (answering "pass") needs a bigger margin than choosing between
# plays: each "not now" looks fine alone, but Forge re-offers the play every window and "later" never comes.
PASS_GATE = float(os.environ.get("EDH_PILOT_PASS_GATE", "0.35"))
ESCALATE_THRESHOLD = float(os.environ.get("EDH_PILOT_ESCALATE", "0.6"))
MAX_ESCALATIONS_PER_GAME = int(os.environ.get("EDH_PILOT_MAX_ESCALATIONS", "8"))
LOG_FULL_STATE = os.environ.get("EDH_PILOT_LOG_STATE", "") not in ("", "0")
PLAN_CHARS = 5000
# Who decides keep or mulligan when a strategist model is in use: "strategist" (one call per opening hand) or "jev".
MULLIGAN_BY = os.environ.get("EDH_MULLIGAN_BY", "strategist")
MULLIGAN_EFFORT = os.environ.get("EDH_MULLIGAN_EFFORT", "medium")
MULLIGAN_SYSTEM = (
    "You decide Commander mulligans for our seat in a 4-player game. Judge this opening hand against our deck plan "
    "and the table: how many lands, and whether they make the colours our commander and the early spells need; "
    "whether cheap card selection or ramp fixes a light or off-colour hand; how soon the plan can start; how fast "
    "the opponents' decks are likely to be. Commander uses the London mulligan (the first mulligan is free), so a "
    "7-card hand that can't cast its spells is worse than a new 7. Answer with exactly KEEP or MULLIGAN on the first "
    "line, then one or two sentences why."
)

STRATEGIST_SYSTEM = (
    "You are the strategist for a Magic: The Gathering Commander deck in a four-player game. A fast "
    "executor model makes each individual decision (casts, attacks, blocks, targets, sacrifices) and "
    "reads your memo before every one. Write for it: concrete, card-named, ordered. Plain text, at most "
    "150 words, four labelled lines: PRIORITIES, THREAT, HOLD, REPLAN IF (specific board events that "
    "would make this plan wrong). HOLD names specific cards or mana to keep back and what for; the "
    "executor treats everything not named there as something to do when it's good. Never put land drops, "
    "fetch-land cracks or other free plays in HOLD unless there is a concrete reason to wait."
)

KIND_GUIDANCE = {
    "action": "Choose the single best action right now (see `window`). Follow the plan and memo. Passing is "
              "not free: you will see these options again in later windows, but deferring a good play every "
              "window means it never happens. Choose `pass` only to keep mana open for a specific instant-speed "
              "answer, or when every listed play actively hurts the plan. A play marked [costs no mana] (fetch "
              "land, free draw, sacrifice outlet) spends none of the mana you are holding. "
              "X questions: pick the X that does what the memo wants (e.g. big enough to kill the target), "
              "within what we can pay. The hold question: keep mana open only for a specific instant-speed play the "
              "memo's HOLD names or that answers a likely threat on opponents' turns; holding costs this turn's plays. A card tagged [the memo HOLDS this card for something specific] is spent only on what the memo holds it for (read the quote; a counterspell held for Pantlaza does not go on another spell): otherwise pass. A play tagged [spends the mana held open for X] cancels that hold: take it when it is worth more to the memo's plan than holding X up. An option that adds several mana to our pool (Vivi Ornitier's ability) is once per turn and its mana empties at the end of the phase: take it when the plays you are about to make this phase need it (an overloaded or X spell), after the cheap spells that grow it, and then spend the mana. "
              "An ability whose cost sacrifices another permanent costs a card: use it when the effect is worth one "
              "(recycling a spent saga, a creature our recursion replays), not for a minor effect like 1 life.",
    "attack": "We are declaring attackers. For this creature, decide whether and whom to attack. Each option says "
              "how Forge's combat rules see it (which blockers could kill it). Weigh the defending player's untapped "
              "blockers, whether we need it back as a blocker, and any chance to finish a player (options tagged "
              "lethal: take it). Otherwise aim by the memo's threat order (options are tagged): the #1 threat first; "
              "prefer it over a player who is merely low on life. If the #1 threat can't be attacked usefully, "
              "attacking another opponent still beats holding back, unless we need this creature as a blocker. "
              "Our commander and the engine pieces the plan names are worth far more than their combat damage: don't "
              "send them where a block can kill them unless the attack wins the game or the memo says to. An attacker "
              "stays tapped through every opponent's next turn and can't block: before sending a creature Forge's AI "
              "keeps home (tagged), check `crack_back`; Forge usually holds a creature because we need it as a blocker. "
              "An option tagged with the memo's own instruction for this creature (\"the memo attacks P2 with this "
              "creature\", \"the memo keeps this creature home\") outranks the threat-order tags: that line is this turn's plan.",
    "block": "An opponent is attacking. Pick a blocker for this attacker or none. `incoming` gives the total damage "
             "if nothing is blocked against our life. Protect engine pieces named in the plan/memo unless the damage "
             "is dangerous; prefer blocks that kill the attacker and survive; chump only when the damage matters.",
    "mulligan": "Opening hand decision. Count lands from the question (and my_hand_summary), not from card "
                "names. A 7-card hand with 0 or 1 land is a mulligan; 2 lands only with cheap ramp or card draw; "
                "3-5 lands with plays by turn 3-4 is a keep; 6+ lands is usually a mulligan. Our commander costs a "
                "lot, so land drops matter more than any single spell.",
    "confirm": "An optional effect asks yes or no. Say yes when it advances our plan at acceptable cost. Paying life "
               "so a land enters untapped is worth it when we will use the mana this turn and our life is healthy; "
               "below about 10 life, keep the life.",
    "choose": "An effect asks us to choose one. Pick what best serves our plan or hurts the biggest threat.",
    "sacrifice": "We must sacrifice a permanent. Lose what hurts the plan least: tokens, spent permanents, or "
                 "cards our recursion can bring back.",
    "sacrifice-cost": "We are paying a sacrifice cost. Sacrifice what hurts the plan least: tokens, spent "
                      "permanents, or cards our recursion can replay; never a key engine piece unless the plan says so. "
                      "If the only things on offer are worth more than the ability's effect (a land or mana rock for "
                      "1 life), cancel the activation.",
    "surveil": "Surveil: keep on top what we want to draw next; put into the graveyard what our graveyard "
               "plan can use or what we don't need.",
    "scry": "Scry: keep on top what we want to draw next; bottom the rest.",
    "trigger-target": "Choose the target for our triggered ability. Aim harmful effects at the key pieces of the "
                      "memo's #1 threat first (options are tagged by the memo's threat order), and beneficial ones at "
                      "our own key permanents.",
    "optional-trigger": "One of our 'you may' triggers is resolving. Say yes when it helps our plan now; no when "
                        "it would hurt us (e.g. a cost we can't afford, a symmetric effect that helps opponents more).",
    "search": "We are searching a zone and take one card (a tutor, fetch land, ramp spell or recursion). Take "
              "the card that most advances the memo's plan from this board (a named tutor target first): the "
              "missing engine piece, the answer to the current top threat, or the land that fixes what our hand needs. Read each land's type "
              "line: a dual or tri land with the searched basic land type makes more colors than the basic and "
              "is usually the better fetch.",
    "discard": "We must discard one card. Each option gives the card's type and mana value. With a graveyard plan, "
               "a permanent card our recursion can replay is the cheapest discard; instants and sorceries are gone for "
               "good. Keep lands and mana sources while we are short of the mana the plan needs, and keep tutors and "
               "the answers the memo earmarks over a mid-size creature.",
    "discard-cost": "We are discarding a card to pay a cost (e.g. Survival of the Fittest). Discard the card the plan "
                    "can use from the graveyard or needs least in hand; never the card the memo is setting up.",
}

ESCALATE_QUESTION = (
    "Compare the board now with the board the `strategy_memo` was written for (see `changes_since_memo`). "
    "Has something happened that makes the memo wrong or dangerously out of date, such as an event its "
    "REPLAN IF line names, a board wipe, removal of our key permanent, a major new threat, or a big life swing?"
)


def _section(md: str, pattern: str, limit: int) -> str:
    m = re.search(rf"^(#+)\s*[^\n]*{pattern}[^\n]*\n(.*?)(?=^\1\s|\Z)", md, re.I | re.M | re.S)
    return m.group(2).strip()[:limit] if m else ""


def deck_plan(brief: Path | None, notes: Path | None) -> str:
    parts = []
    if brief and brief.exists():
        parts.append(brief.read_text()[:PLAN_CHARS])
    if notes and notes.exists():
        md = notes.read_text()
        for pat in ("pilot", "plan", "how to play", "key lines"):
            sec = _section(md, pat, 2500)
            if sec:
                parts.append(f"Pilot notes ({pat}):\n{sec}")
                break
    return "\n\n".join(parts) or "No deck plan provided."


# --------------------------------------------------------------------------- board diffs



# A battlefield entry from StateView: "Name[ P/T][ [token]][ [land]][ {counters}][ xN][ (tapped k)]".
_ENTRY = re.compile(r"^(?P<name>.+?)(?P<pt> -?\d+/-?\d+)?(?P<token> \[token\])?(?P<land> \[land\])?"
                    r"(?: \{.*?\})?(?: \[(?:wearing|paired with) [^\]]*\])*(?: x(?P<n>\d+))?(?: \(tapped \d+\))?$")


def parse_entry(entry: str) -> dict:
    m = _ENTRY.match(entry)
    if not m:
        return {"name": entry, "n": 1, "creature": False, "token": False, "land": False}
    return {"name": m["name"], "n": int(m["n"] or 1), "creature": bool(m["pt"]),
            "token": bool(m["token"]), "land": bool(m["land"])}


_MEMO_HEAD = re.compile(r"^(THIS TURN|NEXT TURNS|TARGET|WIN PATH|THREAT ORDER|THREATS & ANSWERS|HOLD|REPLAN IF|PRIORITIES|THREAT)"
                        r"\b[^:\n]*:?", re.M)
_OPTION_CARD = re.compile(r"^(?:cast|activate|play land) (.+?) \(from ")


# A "Next turn: ..." bullet inside THIS TURN is a later turn's plan: tagged as a current step, it cast cards a turn
# early (round 5 audit, two games)
_LATER_TURN = re.compile(r"\n\s*(?:[-*•]\s*)?(?:Next turn|The turn after|Then next turn|On our next turn|Next round)\b",
                         re.I)


@functools.lru_cache(maxsize=64)
def memo_sections(memo: str) -> dict:
    """The memo's labelled lines (THIS TURN, HOLD, ...) by label."""
    heads = list(_MEMO_HEAD.finditer(memo or ""))
    secs = {m.group(1): memo[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(memo)]
            for i, m in enumerate(heads)}
    later = _LATER_TURN.search(secs.get("THIS TURN", ""))
    if later:
        this = secs["THIS TURN"]
        secs["THIS TURN"] = this[:later.start()]
        secs["NEXT TURNS"] = this[later.start():] + ("\n" + secs["NEXT TURNS"] if secs.get("NEXT TURNS") else "")
    return secs


# Names the memo may use for a card besides its full name. A strategist writes "Vivi", "Bolt", "Ballista":
# in a one-game Vivi test the memo said "cast Vivi" on three turns running, the Vivi option was never tagged,
# and Jev cast the other cards the tags pointed at. A nickname counts only if no other card of ours (or on
# offer) shares it: "Lightning" is Lightning Bolt's only while there is no Lightning Greaves.
_ALIAS_SKIP = {"Island", "Mountain", "Forest", "Swamp", "Plains", "Wastes", "Command", "Tower", "Token", "Land"}
_DECK_NAMES: frozenset[str] = frozenset()


def set_deck_names(names) -> None:
    """Our decklist's card names, so nicknames can be checked for uniqueness against the whole deck."""
    global _DECK_NAMES
    _DECK_NAMES = frozenset(names)
    _aliases.cache_clear()


@functools.lru_cache(maxsize=4096)
def _aliases(name: str, others: frozenset[str] = frozenset()) -> tuple[str, ...]:
    front = name.split(" // ")[0]
    before_comma = front.split(",")[0]
    pool = [o.split(" // ")[0] for o in (others | _DECK_NAMES) if o.split(" // ")[0] != front]
    out = [name, front]
    if before_comma != front and not any(o.split(",")[0] == before_comma for o in pool):
        out.append(before_comma)
    words = re.findall(r"[A-Z][\w'-]*", before_comma)
    for w in dict.fromkeys(words[:1] + words[-1:]):
        if (len(w) >= 4 and w not in _ALIAS_SKIP and w != before_comma
                and not any(re.search(r"(?<![\w'-])" + re.escape(w) + r"(?![\w'-])", o) for o in pool)):
            out.append(w)
    return tuple(dict.fromkeys(out))


def _card_matches(text: str, name: str, others: frozenset[str] = frozenset()) -> list[int]:
    """Positions where the memo text names the card, by full name or an unambiguous nickname (case-sensitive)."""
    at = set()
    for a in _aliases(name, others):
        at.update(m.start() for m in re.finditer(r"(?<![\w'-])" + re.escape(a) + r"(?![\w'-])", text))
    return sorted(at)


def _find_card(text: str, name: str, others: frozenset[str] = frozenset()) -> int:
    hits = _card_matches(text, name, others)
    return hits[0] if hits else -1


# "1. Play Island." at a line start, or an inline "2) ..."; not a number ending a sentence ("... costs 0. Then").
_HOLD_WORDS = re.compile(r"\b(hold|keep|save|reserve|leave|don't|do not|never|until)\b", re.I)
_PLAY_VERB = re.compile(r"\b(cast|recast|play|activate|equip|flash|crack|tap|overload|sacrifice|fire|use|fetch|search|"
                        r"tutor|return|move|put|chain|then|evoke|flashback|escape|foretell|unearth|dash|blitz|cycle|"
                        r"channel|ninjutsu|suspend|bestow|mutate|crew|kick|deploy|drop|land|resolve|slam|reanimate|"
                        r"ping|bounce|counter|kill|exile|destroy)\b", re.I)
_PAYING = re.compile(r"\b(with|using|tapping|off|from|for|plus|and|by)\s+([\w,'{}+-]+\s+){0,4}$", re.I)


def _mention_kind(prefix: str) -> str:
    """How the words before a card name in the plan use it: 'hold', 'play' or a plain 'mention'."""
    # "Hold priority and cast An Offer You Can't Refuse" plays the Offer
    if _HOLD_WORDS.search(re.sub(r"\bhold(?:ing)? priority\b", "", prefix, flags=re.I)):
        return "hold"
    if re.fullmatch(r"[\s\-*]*(\d+[.)])?\s*", prefix):  # the card leads the clause: "Ponder.", "Bolt Braids"
        return "play"
    verbs = list(_PLAY_VERB.finditer(prefix))
    pay = _PAYING.search(prefix)
    if verbs and not (pay and pay.start() > verbs[-1].start()):  # "for {C}, then cast X" plays X; "cast Y with X" doesn't
        return "play"
    return "mention"


_ACT_VERBS = re.compile(r"\b(tap|activate|use|crack|sacrifice|equip)\b")
_CAST_VERBS = re.compile(r"\b(cast|recast|evoke|flashback|overload|kick)\b")
_NOT_HELD = re.compile(r"\b(after|once|when|since|because|if|unless|nothing|none|no)\b", re.I)
# a numbered step: at a line start ("2. Cast X"), inline with a parenthesis ("... 2) Cast X"), or inline after a
# sentence ends ("... P2 to 4. 3. Cast Windfall"); "for 6. 7 left" is not a step because "7" isn't followed by ". "
_STEP = re.compile(r"(?m)(?:^[ \t-]*(\d+)[.)]\s|(?<=\s)(\d+)\)\s|(?<=[.;!?]\s)(\d+)\.\s)")
_FALLBACK = re.compile(r"\binstead\b|\botherwise\b|^\W*(?:if|unless|else)\b", re.I)


def _step_starts(plan: str) -> list[tuple[int, str]]:
    """(position, number) of each numbered step. An inline "N)" inside parentheses is not a step: "({1}{U}{R} plus
    tax 2) " read as step 2. Parentheses are counted without the steps' own "N)" markers."""
    out, marker_closes = [], set()
    for m in _STEP.finditer(plan):
        for g in (1, 2, 3):
            if not m.group(g):
                continue
            pos = m.start(g)
            if g == 2:
                closes = sum(1 for i, ch in enumerate(plan[:pos]) if ch == ")" and i not in marker_closes)
                if plan.count("(", 0, pos) > closes:
                    continue
            out.append((pos, m.group(g)))
            if g in (1, 2) and plan[m.end(g):m.end(g) + 1] == ")":
                marker_closes.add(m.end(g))
    return out


def _step_around(plan: str, at: int) -> tuple[str | None, str, bool]:
    """The numbered step containing position `at` (number, its text), and whether the card is named there only in
    a conditional clause ("If the cost shows 5, cast Guttersnipe instead")."""
    starts = _step_starts(plan)
    before = [s for s in starts if s[0] <= at]
    begin, num = before[-1] if before else (0, None)
    end = next((s[0] for s in starts if s[0] > at), len(plan))
    step = plan[begin:end]
    sentence = next((s for s in re.split(r"(?<=[.;!?])\s+", step)
                     if begin + step.find(s) <= at < begin + step.find(s) + len(s)), step)
    text = " ".join((step if num else sentence).split())  # an unnumbered plan: the sentence that names the card
    return num, (text[:200] + "…" if len(text) > 200 else text), bool(_FALLBACK.search(sentence))


def _overload_planned(plan: str, name: str, others: frozenset[str] = frozenset()) -> bool:
    """Whether the plan casts this card with overload: the overload must govern this card, not another in the step."""
    for a in _aliases(name, others):
        n = re.escape(a)
        if re.search(rf"\boverload\w*\s+(?:the\s+|our\s+)?{n}\b", plan, re.I) or \
                re.search(rf"\b{n}\b(?:\s*\([^)]*\))?\s+(?:overloaded|with (?:its )?overload|for (?:its )?overload)",
                          plan, re.I):
            return True
    return False


def plan_marker(memo: str, option_text: str, fresh: bool = True, others: frozenset[str] = frozenset()) -> str:
    """Tag for an action option whose card the memo's plan for this turn or its HOLD line names.

    fresh: the memo was written this turn, so THIS TURN is the plan; otherwise (a memo meant to last several
    turns) THIS TURN is done and NEXT TURNS is the plan.

    Jev reads the whole memo, but matching card names across 20-odd options is where it slips: in the v3.1
    post-mortem the most common game-losing mistake was a planned play left unmade while it was on offer.
    """
    m = _OPTION_CARD.match(option_text)
    if not m:
        return ""
    tag = card_marker(memo, m.group(1), fresh, others, option_text.split(" ", 1)[0])
    # The memo may name a mode: "overload Cyclonic Rift". Tag the other mode as such, not as the plan: in a Vivi
    # game the single-target Rift carried the plan's tag and was cast in place of the planned overload. Read it from
    # the whole plan, not the tag's quote (cut at 200 characters), and in every wording: "overload Cyclonic Rift",
    # "Cyclonic Rift overloaded", "Cyclonic Rift with overload".
    if tag and ("plan" in tag):
        secs = memo_sections(memo)
        plan = (secs.get("THIS TURN") or secs.get("PRIORITIES") or "") if fresh else secs.get("NEXT TURNS", "")
        overload_planned = _overload_planned(plan, m.group(1), others)
        is_overload = "overload {" in option_text.lower()
        if not overload_planned and not is_overload:
            return tag
        q = re.search(r'"(.*)"', tag)
        quote = f': "{q.group(1)}"' if q else ""
        hold = "; named in the memo's HOLD line" if "HOLD line" in tag else ""
        if overload_planned and not is_overload:
            tag = f" [the memo overloads this card; this option is its single-target mode{quote}{hold}]"
        elif is_overload and not overload_planned:
            tag = f" [the memo casts this card without overload; this option is the overload{quote}{hold}]"
    return tag


def card_marker(memo: str, name: str, fresh: bool = True, others: frozenset[str] = frozenset(), verb: str = "") -> str:
    """plan_marker for a card name: where the memo's plan for this turn or its HOLD line names it, quoting the
    step, so a card the plan names only as a fallback reads as one ("named in the memo's THIS TURN fallback")."""
    if not memo:
        return ""
    secs, tags = memo_sections(memo), []
    label = "THIS TURN" if fresh else "NEXT TURNS"
    plan = (secs.get("THIS TURN") or secs.get("PRIORITIES") or "") if fresh else secs.get("NEXT TURNS", "")
    found = []
    for at in _card_matches(plan, name, others):
        num, text, fallback = _step_around(plan, at)
        start = max(plan.rfind(". ", 0, at), plan.rfind("\n", 0, at), plan.rfind(";", 0, at), plan.rfind(": ", 0, at)) + 1
        found.append((num, text, fallback, _mention_kind(plan[start:at]), " ".join(plan[start:start + 260].split()),
                      plan[start:at].lower()))
    found = [f for f in found if f[2] or f[3] != "mention"]  # commentary ("so Mana Sculpt gives no mana") isn't a plan
    if found:
        plays = [f for f in found if not f[2] and f[3] == "play"]
        any_play = bool(plays)
        # A step whose verb is the other kind of play isn't this option's step: "Cast Swiftfoot Boots" doesn't plan
        # equipping it, and "Activate Vivi Ornitier for 6" doesn't plan casting her. A step with no verb (the card
        # leads the clause, "1) Brainstorm.") fits either.
        acts, casts = _ACT_VERBS, _CAST_VERBS
        if verb == "activate":  # "Tap Vivi Ornitier for 10 mana" is the step for her mana, not "Cast Vivi Ornitier"
            plays = [f for f in plays if acts.search(f[5]) or not casts.search(f[5])]
            plays.sort(key=lambda f: 0 if acts.search(f[5]) else 1)
        elif verb == "cast":
            plays = [f for f in plays if casts.search(f[5]) or not acts.search(f[5])]
            plays.sort(key=lambda f: 0 if casts.search(f[5]) else 1)
        holds = [f for f in found if f[3] == "hold"]
        if plays:
            num, text = plays[0][0], plays[0][1]
            tags.append(f"named in the memo's {label} plan" + (f", step {num}" if num and fresh else "") + f': "{text}"')
        elif holds:  # "Hold {1}{U}{U} for Mana Sculpt... Earmarks: 1. Pantlaza": a hold, with what it's held for
            tags.append(f'the memo HOLDS this card for something specific: "{holds[0][4]}"')
        elif any_play:  # planned, but as the other kind of play (cast vs activate): not this option
            pass
        else:
            num, text = found[0][0], found[0][1]
            tags.append(f"named in the memo's {label} fallback" + (f", step {num}" if num and fresh else "") + f': "{text}"')
    hold_line = secs.get("HOLD", "")
    at = _find_card(hold_line, name, others)
    # the HOLD line may name a card only as a reference point ("Nothing castable remains after Niv-Mizzet"); that
    # is not a hold of the card
    if at >= 0 and _NOT_HELD.search(hold_line[max(hold_line.rfind(". ", 0, at), hold_line.rfind(";", 0, at)) + 1:at]):
        at = -1
    if at >= 0:
        start = max(hold_line.rfind(". ", 0, at), hold_line.rfind(";", 0, at)) + 1
        tags.append(f'named in the memo\'s HOLD line: "{" ".join(hold_line[start:start + 200].split())}"')
    return f" [{'; '.join(tags)}]" if tags else ""


# What an opponent's trigger punishes, from its rules text; checked in order, first match wins.
_FEEDS = [
    (re.compile(r"whenever [^.]*?\bcreatures? (?:or planeswalkers? )?you control dies", re.I),
     "their creatures dying (our removal feeds it)"),
    (re.compile(r"whenever [^.]*?\bcreature an opponent controls dies", re.I), "our creatures dying"),
    (re.compile(r"whenever [^.]*?\b(?:a|another) (?:nontoken )?creature (?:or planeswalker )?dies", re.I),
     "any creature dying (our removal and sacrifices feed it)"),
    (re.compile(r"whenever a player sacrifices", re.I), "any sacrifice, ours included"),
    (re.compile(r"whenever (?:a player|an opponent) casts a spell from a graveyard|enters from a graveyard", re.I),
     "our graveyard casts"),
    (re.compile(r"whenever an opponent casts|whenever a player casts", re.I), "our spells"),
]


def feed_hazards(state: dict, limit: int = 8) -> list[str]:
    """Opponents' permanents and emblems whose triggers our own plays feed (Blood Artist, Grave Pact,
    Sephiroth's emblem, Rhystic Study...). Their text is in the state already; this makes them hard to miss:
    feeding them lost games in the v3.1 post-mortem."""
    texts, out = state.get("card_text", {}), []
    for p in state.get("players", []):
        if p.get("is_me") or p.get("lost"):
            continue
        names = [parse_entry(e)["name"] for e in p.get("battlefield", [])] + list(p.get("command_zone_effects", []))
        for name in dict.fromkeys(names):
            text = texts.get(name, "")
            for rx, what in _FEEDS:
                if rx.search(text):
                    out.append(f"{p['name']} {name}: triggers on {what}")
                    break
    return out[:limit]


_PLAYER = re.compile(r"\b(P[1-9])\b")


def threat_order(memo: str, state: dict) -> list[str]:
    """The opponents in the order the strategist ranks them (its THREAT ORDER line), alive ones only. Memos
    without that line fall back to the players behind its ranked THREATS & ANSWERS items, so older logs and
    a forgotten line still give an order."""
    if not memo:
        return []
    alive = [p["name"] for p in state.get("players", []) if not p.get("is_me") and not p.get("lost")]
    secs = memo_sections(memo)
    order: list[str] = []
    line = secs.get("THREAT ORDER", "")
    if line:
        head = re.split(r"[.;\n]|—| - ", line.strip(), maxsplit=1)[0] if ">" in line else line
        order = [m for m in _PLAYER.findall(head if ">" in head else line)]
    if not order:
        owners = {}
        for p in state.get("players", []):
            if p.get("is_me"):
                continue
            for n in [parse_entry(e)["name"] for e in p.get("battlefield", [])] + (p.get("commanders") or []):
                short = n.split(" // ")[0].split(",")[0]
                if len(short) > 4:
                    owners.setdefault(short, p["name"])
        for item in re.split(r"\n|(?=\b\d[.)]\s)", secs.get("THREATS & ANSWERS", "")):
            if not re.match(r"\s*\d[.)]", item):
                continue
            m = _PLAYER.search(item)
            who = m.group(1) if m else next((o for n, o in owners.items() if n in item), None)
            if who:
                order.append(who)
    return [p for p in dict.fromkeys(order) if p in alive]


_TARGET_OWNER = re.compile(r"\[(P\d)[,\]]")


def threat_tag(order: list[str], kind: str, option_text: str, memo: str = "") -> str:
    """Tag an attack or target option with the memo's threat rank of the player it hits. A target option is ranked
    when it is the player (their face) or a permanent the memo names: ranking every creature of the #1 threat sent 8
    Niv-Mizzet pings into a 9/9 Zacama while the memo said to aim them at P1's face."""
    if not order:
        return ""
    if kind == "attack":
        m = re.match(r"attack (P\d)\b", option_text)
    else:
        m = re.match(r"(P\d) \(-?\d+ life", option_text)
        if not m and "[ours" not in option_text:
            m = _TARGET_OWNER.search(option_text)
            name = option_text.split(" [")[0].strip()
            if (m and memo and not option_text.startswith(("cast ", "activate ", "play land "))
                    and not any(re.search(rf"\b{re.escape(a)}\b", memo, re.I) for a in _aliases(name))):
                return ""
    if not m or m.group(1) not in order:
        return ""
    k = order.index(m.group(1)) + 1
    return " [the memo's #1 threat]" if k == 1 else f" [memo threat #{k}]"


_AVOID = re.compile(r"\b(?:never|don't|do not|no)\s+(?:target|ping|pings? at|hit|bolt|burn|shoot|damage|aim \w+ at)"
                    r"\s+([^.;\n]+)", re.I)
_DB = None


@functools.lru_cache(maxsize=4096)
def _subtypes(name: str) -> frozenset[str]:
    """A card's creature types, lowercased, from the card database ("Dinosaur" for Zacama)."""
    global _DB
    try:
        if _DB is None:
            from .cards import CardDB
            _DB = CardDB()
        c = _DB.get(name)
        line = (c.type_line if c else "") or ""
    except Exception:
        return frozenset()
    return frozenset(w.lower() for w in line.split("—", 1)[1].split()) if "—" in line else frozenset()


def avoid_tag(memo: str, option_text: str) -> str:
    """"Never ping Dinosaurs", "don't target Teval": a target the memo rules out, by name or creature type."""
    if not memo or "[ours" in option_text or re.match(r"(?:P\d|us) \(", option_text):
        return ""
    name = option_text.split(" [")[0].strip()
    for m in _AVOID.finditer(memo):
        phrase = m.group(1)
        if any(re.search(rf"\b{re.escape(a)}\b", phrase, re.I) for a in _aliases(name)):
            return " [the memo says not to target this]"
        types = _subtypes(name)
        if types and any(w.lower().rstrip("s") in types or w.lower() in types for w in re.findall(r"[A-Za-z]+", phrase)):
            return " [the memo says not to target this]"
    return ""


_ATTACKER_PT = re.compile(r"(\d+)/(\d+)\?\s*$")
_DEFENDER = re.compile(r"^attack (P\d) \((-?\d+) life\)")


def lethal_tags(questions: list[dict]) -> dict[tuple[str, str], str]:
    """For an attack declaration: players whom the attackers no untapped creature can block would kill
    together (their total power at least the player's life). Arithmetic the executor shouldn't have to do;
    without it a 4-power unblockable attack on a player at 4 life was declined as "just a low life total"."""
    safe, life, who = defaultdict(int), {}, defaultdict(list)
    for q in questions:
        m = _ATTACKER_PT.search(q.get("prompt", ""))
        if not m:
            continue
        power = int(m.group(1))
        for o in q["options"]:
            d = _DEFENDER.match(o["text"])
            if d and "no untapped creature of theirs can block it" in o["text"]:
                safe[d.group(1)] += power
                life[d.group(1)] = int(d.group(2))
                who[d.group(1)].append((q["id"], o["id"]))
    out = {}
    for p, total in safe.items():
        if 0 < life[p] <= total:
            for key in who[p]:
                out[key] = f" [lethal: our unblockable attackers at {p} total {total} power, {p} has {life[p]} life]"
    return out


_ATTACKER = re.compile(r"^Attack with (.+?) \[")
_HOME = re.compile(r"\b(stays? home|keep\b.*\bhome|don't attack|do not attack|no attacks?|hold\b.*\bback|not attack)\b", re.I)
_OTHERS = re.compile(r"\b(the others|the rest|everything else|all others|nothing else|other creatures)\b", re.I)


def attack_plan_tags(memo: str, fresh: bool, questions: list[dict]) -> dict[tuple[str, str], str]:
    """Tags for attack options from the memo's own attack instructions ("Attack P2 with Bird Token only", "Harmonic
    Prodigy and Guttersnipe stay home"). Only the threat rank reached attack options before, so when THIS TURN said
    "attack P2 with the Bird only" and the threat order ranked P1 first, the Bird went at P1 and Prodigy attacked too."""
    secs = memo_sections(memo)
    plan = (secs.get("THIS TURN") or "") if fresh else secs.get("NEXT TURNS", "")
    if not plan:
        return {}
    attackers = {}
    for q in questions:
        m = _ATTACKER.match(q.get("prompt", ""))
        if m:
            attackers[q["id"]] = m.group(1)
    out = {}
    sentences = [s for s in re.split(r"(?<=[.;!?])\s+|\n", plan) if re.search(r"\battack|\bhome\b|\bswing", s, re.I)]

    def names_in(s: str) -> set[str]:
        return {qid for qid, n in attackers.items() if _card_matches(s, n) or n.lower() in s.lower()}

    # "the others" means the creatures the plan doesn't send anywhere
    sent = set().union(*[names_in(s) for s in sentences
                         if re.search(r"\b(?:attack|swing at|hit)\s+P\d\b", s, re.I) and not _HOME.search(s)] or [set()])
    for s in sentences:
        quote = " ".join(s.split())[:160]
        target = re.search(r"\b(?:attack|swing at|hit)\s+(P\d)\b", s, re.I)
        named = names_in(s)
        home, others = _HOME.search(s), _OTHERS.search(s)
        only = re.search(r"\b(alone|only)\b", s, re.I)
        blanket = home and not named and not target and not others  # "No attacks unless lethal."
        for qid in attackers:
            if blanket:
                out[(qid, "hold")] = f' [the memo says no attacks: "{quote}"]'
            elif home and (qid in named or (others and qid not in named and qid not in sent)):
                out[(qid, "hold")] = f' [the memo keeps this creature home: "{quote}"]'
            elif target and qid in named:
                out[(qid, "attack " + target.group(1))] = f' [the memo attacks {target.group(1)} with this creature: "{quote}"]'
            elif target and only and named and qid not in named:
                out[(qid, "hold")] = f' [the memo attacks {target.group(1)} only with other creatures: "{quote}"]'
    return out


def forge_pick_tag(q: dict, oid: str) -> str:
    """Which attack option is Forge's own: holding back is usually its read that we need the blocker."""
    if oid != q.get("default"):
        return ""
    return " [Forge's AI keeps it home]" if oid == "hold" else " [Forge's AI's pick]"


def crack_back(state: dict) -> dict:
    """For attack declarations: what the opponents could swing back at us with. Our attackers stay tapped through
    their turns. In the attack-only ablation arm, Jev's attack overrules were mostly sending creatures Forge kept
    home into lanes nobody could block; the option text said the attacker was safe, not that home wasn't: we took
    189 damage in the two rounds after those overrules against 135 on the same games under Forge."""
    me = next((p for p in state.get("players", []) if p.get("is_me")), None)
    if not me:
        return {}
    power = {}
    for p in state.get("players", []):
        if p.get("is_me") or p.get("lost"):
            continue
        total = 0
        for entry in p.get("battlefield", []):
            m = _ENTRY.match(entry)
            if m and m["pt"]:
                total += max(0, int(m["pt"].split("/")[0])) * int(m["n"] or 1)
        power[p["name"]] = total
    life = me.get("life", 0)
    out = {"our_life": life,
           "their_creature_power": power,
           "note": "all of their creatures untap before they attack; ours that attack now stay tapped until our turn"}
    big = [n for n, v in power.items() if v >= life]
    if big:
        out["warning"] = f"{', '.join(big)} alone could deal us lethal ({life} life) if we leave no blockers"
    return out


_INCOMING = re.compile(r"deal (\d+) combat damage; our life is (-?\d+)")


def block_lethal(req: dict) -> tuple[int, int] | None:
    """(unblocked damage, our life) when the attackers at us are lethal unblocked; else None."""
    m = _INCOMING.search(str(req.get("incoming", "")))
    if m and int(m.group(1)) >= int(m.group(2)):
        return int(m.group(1)), int(m.group(2))
    return None


def option_tags(req: dict, memo: str, age: int = 0) -> dict[str, dict[str, str]]:
    """The memo-derived tags on each option of a request: planned / held plays on actions, the threat rank of
    the player an attack or target hits, and lethal attacks. qid -> option id -> tag text ("" when none)."""
    kind, state = req.get("kind", "action"), req.get("state", {})
    order = threat_order(memo, state) if kind in ("attack", "trigger-target", "action") else []
    lethal = lethal_tags(req.get("questions", [])) if kind == "attack" else {}
    atk = attack_plan_tags(memo, age == 0, req.get("questions", [])) if (kind == "attack" and memo) else {}
    out = {}
    offered = frozenset(m.group(1) for q in req.get("questions", []) if q["id"] == "action"
                        for o in q["options"] if (m := _OPTION_CARD.match(o["text"])))
    lethal_in = block_lethal(req) if kind == "block" else None
    for q in req.get("questions", []):
        if lethal_in:  # Jev declined chump blocks Forge made while the attack was lethal, twice, and we died
            out[q["id"]] = {o["id"]: (f" [unblocked, the attackers deal {lethal_in[0]} and we have {lethal_in[1]} life: "
                                      "not blocking loses the game]" if o["id"] == "none" else "") for o in q["options"]}
            continue
        if kind in ("search", "discard") and re.search(r"\[hand\]|from (?:our )?hand|discard", q.get("prompt", ""), re.I):
            out[q["id"]] = {o["id"]: keep_tag(memo, o["text"], age == 0) for o in q["options"]}
            continue
        mark = kind == "action" and q["id"] == "action"
        aim = kind if kind == "attack" else "target" if (kind == "trigger-target" or q["id"].startswith("tgt_") or mark) else ""
        out[q["id"]] = {o["id"]: (_timed(plan_marker(memo, o["text"], age == 0, offered), req) if mark else "")
                        + (threat_tag(order, aim, o["text"], memo) if aim else "")
                        + (avoid_tag(memo, o["text"]) if aim == "target" else "") + lethal.get((q["id"], o["id"]), "")
                        + (forge_pick_tag(q, o["id"]) if kind == "attack" else "")
                        + (next((v for (qid, lead), v in atk.items() if qid == q["id"]
                                 and (o["id"] == "hold" if lead == "hold" else o["text"].startswith(lead + " "))), "")
                           if atk else "")
                        for o in q["options"]}
    return out


_TIMED = re.compile(r"\b(?:on (?:P\d|an opponent|each opponent|their)'?s? (?:turn|combat|end step|upkeep|attack)"
                    r"|at the beginning of (?:P\d|their|an opponent)|during (?:P\d|their|an opponent)'?s?"
                    r"|in response to|at (?:P\d|their|an opponent)'s end step|at the end of (?:P\d|their|an opponent)"
                    r"|when (?:P\d|they|an opponent) (?:attacks?|casts?|declares?)|before (?:P\d|their) (?:blockers|damage))",
                    re.I)


def _timed(tag: str, req: dict) -> str:
    """A planned play the memo times for an opponent's turn ("Cyclonic Rift at the beginning of P3's combat") is a
    hold in our own windows: Rift was cast in P2's combat and Pongify at our own end of combat, off their windows."""
    st = req.get("state") or {}
    # whose turn it is, not the window's wording: our combat steps were labelled "instant-speed window", so Pongify
    # timed for P3's combat was cast in our own
    ours = (st["active"] == st["me"]) if st.get("active") and st.get("me") else str(req.get("window", "")).startswith("our ")
    if " plan" not in tag or "fallback" in tag or not ours:
        return tag
    q = re.search(r'plan[^"]*"([^"]*)"', tag)  # the plan step's quote only, not a later HOLD or threat quote
    if q and _TIMED.search(q.group(1)):
        return f' [the memo HOLDS this card for something specific: "{q.group(1)}"]'
    return tag


_DISPOSE = re.compile(r"\b(?:discard(?:ing)?|put(?:ting)? back|put\b[^.;]{0,20}\bon (?:top|the bottom)|bottom|pitch)\b", re.I)
_NEGATION = re.compile(r"\b(?:never|don't|do not|not|no|nothing|avoid)\b", re.I)
_DISPOSE_END = re.compile(r"\b(?:keep|keeping|except|but|save|hold|holding|not)\b", re.I)


def _disposed(memo: str, name: str) -> bool:
    """Whether the memo throws this card away: named after a disposal verb in the same sentence ("Discard Fire Magic
    first, then Archmage of Runes"), unless the verb is negated ("Never discard Negate") or the name comes after a
    keep clause ("Discard the weakest cards and keep An Offer You Can't Refuse"): both read as discards in round 6,
    and Jev threw away An Offer and Counterspell."""
    for sent in re.split(r"[.;:\n]", memo or ""):
        for v in _DISPOSE.finditer(sent):
            if _NEGATION.search(sent[:v.start()][-30:]):
                continue
            rest = sent[v.end():]
            stop = _DISPOSE_END.search(rest)
            rest = rest[:stop.start()] if stop else rest
            if any(re.search(rf"\b{re.escape(a)}\b", rest, re.I) for a in _aliases(name)):
                return True
    return False


def keep_tag(memo: str, option_text: str, fresh: bool) -> str:
    """For a card we're choosing to put back or throw away: whether the memo plans to play or holds it. Brainstorm's
    put-back had no memo tags, and Jev put back Windfall, the card step 3 of a lethal plan cast that turn."""
    name = re.split(r" — | \[|: ", option_text, maxsplit=1)[0].strip()
    tag = card_marker(memo, name, fresh, verb="cast") if name else ""
    if "HOLD" in tag:  # the HOLD line keeps it, whatever a discard sentence lists
        return " [the memo holds this card: keep it in hand]" + tag
    if name and _disposed(memo, name):
        return " [the memo discards or puts back this card]"
    if " plan" in tag and "fallback" not in tag:
        return " [the memo plays this card this turn: keep it in hand]" + tag
    if "HOLD" in tag:
        return " [the memo holds this card: keep it in hand]" + tag
    return ""


def ai_blind_cards(deck_path: Path | None) -> frozenset[str]:
    """Cards in the deck that Forge's AI never plays (flagged in Forge's card scripts or never cast in our logs)."""
    if not deck_path:
        return frozenset()
    try:
        from . import forge
        from .cards import CardDB
        from .deck import Deck
        deck = Deck.load(Path(deck_path))
        deck.resolve(CardDB())
        return frozenset(forge.support_report(deck)["ai_cannot_play"])
    except Exception:  # noqa: BLE001 - a missing Forge install just means no such cards are known
        return frozenset()


BLIND_TAG = " [Forge's AI can't play this card]"


_EQUIP = re.compile(r"^activate (.+?) \(from Battlefield\): Equip\b")
STRATEGIST_RETRY_S = 15  # wait before the one retry of a failed strategist call
LIBRARY_FLOOR = 12  # below this many cards in our library, pings avoid opponents' faces (draw engines)
_DRAWS_ON_DAMAGE = re.compile(r"deals (?:combat )?damage to (?:an opponent|a player)[^.]*?,? (?:you may )?draw", re.I)


def _draw_on_damage(state: dict) -> bool:
    """Whether damage we deal to an opponent draws us cards: a Tandem Lookout pairing, Ophidian Eye and the like."""
    me = next((p for p in state.get("players", []) if p.get("is_me")), {})
    texts = state.get("card_text", {})
    for e in me.get("battlefield", []):
        if "[paired with" in e or "Tandem Lookout" in e:
            return True
        worn = re.search(r"\[wearing ([^\]]*)\]", e)
        names = [parse_entry(e)["name"]] + ([w.strip() for w in worn.group(1).split(",")] if worn else [])
        if any(_DRAWS_ON_DAMAGE.search(texts.get(n, "")) for n in names):
            return True
    return False
_WRONG_MODE = re.compile(r"this option is (?:its single-target mode|the overload)")
_X_CARD = re.compile(r"^If we (?:cast|activate) (.+?) \(")
_HOLD_CARD = re.compile(r"\) for (.+?): ")


def _blind(name: str | None, blind: frozenset[str]) -> bool:
    return bool(name) and (name in blind or name.split(" // ")[0] in blind)


def steer_tags(req: dict, memo: str, age: int = 0, blind: frozenset[str] = frozenset()) -> dict[str, dict[str, str]]:
    """option_tags, plus the memo's plan / HOLD marker on the X values of a card the memo names and on holding
    mana for one. Steer mode only; Jev isn't shown these. Without them an X value or a hold is Jev's own
    tactical call: in the static-plan steer arm, 29 of 31 overrules were Walking Ballista cast for X = 0.

    blind: cards Forge's AI never plays. Their plays, and the X values and targets for them, are tagged: Forge
    has no view there to keep. With Vivi, the pilot cast five such cards (Windfall, Faithless Looting, ...)
    about once a game while Forge never did, and placed 0.21 ± 0.13 better than Forge over 94 paired games."""
    out, fresh = option_tags(req, memo, age), age == 0
    for q in req.get("questions", []):
        if q["id"] == "action" and req.get("kind", "action") == "action":
            for o in q["options"]:
                m = _OPTION_CARD.match(o["text"])
                if m and not o["text"].startswith("play land") and _blind(m.group(1), blind):
                    out["action"][o["id"]] += BLIND_TAG
        elif q["id"].startswith(("x_", "tgt_")):
            m = _X_CARD.match(q["prompt"])
            card = m.group(1) if m else None
            if _blind(card, blind):
                out[q["id"]] = {o["id"]: out[q["id"]].get(o["id"], "") + BLIND_TAG for o in q["options"]}
            elif q["id"].startswith("x_"):
                mark = card_marker(memo, card, fresh) if card else ""
                out[q["id"]] = {o["id"]: "" if o["id"] == q.get("default") else mark for o in q["options"]}
        elif q["id"] == "hold":
            out["hold"] = {o["id"]: card_marker(memo, m.group(1), fresh) if (m := _HOLD_CARD.search(o["text"])) else ""
                           for o in q["options"]}
    return out


def steer_reason(kind: str, qid: str, choice: str, default: str, tags: dict[str, str]) -> str:
    """Steer mode: why Jev may overrule Forge here, or "" if it may not. Only for something the memo asks
    for that Forge's answer lacks: the #1 threat, a lethal attack, not firing a held card, an X value for a
    card the memo names, or holding mana for the memo's instant.

    Not a planned play: making the play the memo's THIS TURN names instead of Forge's was 14 of the Opus steer
    arm's 19 overrules a game, and that arm placed +0.39 ± 0.17 worse than Forge on the same games, the same
    as Jev choosing actions on its own judgement (+0.37)."""
    mine, forge = tags.get(choice, ""), tags.get(default, "")
    if BLIND_TAG in mine:
        return "a card Forge's AI can't play"
    if qid.startswith("x_") or qid == "hold":
        return "sizing / holding per the memo" if "the memo's" in mine else ""
    if "lethal" in mine and "lethal" not in forge:
        return "lethal"
    if "#1 threat" in mine and "#1 threat" not in forge and not (kind == "attack" and default == "hold"):
        return "the memo's #1 threat"  # attacks: whom to hit, not whether (Forge's hold weighs our defence)
    if kind == "action" and qid == "action" and choice == "pass" and "HOLD" in forge:
        return "the memo holds Forge's play"
    return ""


def _board_counts(state: dict) -> dict:
    out = {}
    for p in state.get("players", []):
        perms = creatures = 0
        named = set()
        for entry in p.get("battlefield", []):
            e = parse_entry(entry)
            if e["land"]:
                continue
            perms += e["n"]
            creatures += e["n"] if e["creature"] else 0
            if not e["token"]:
                named.add(e["name"])
        out[p["name"]] = {"me": p.get("is_me"), "life": p.get("life", 0), "nonland": perms,
                          "creatures": creatures, "lost": p.get("lost", False), "named": named}
    return out


def changes_since(memo_state: dict | None, state: dict, ours: set[str] = frozenset()) -> list[str]:
    """Notable, code-computed differences between two board snapshots.

    `ours`: names of our permanents we used up on purpose since the memo (cracked a fetch,
    sacrificed for a cost, activated a self-sacrificing artifact). They are not news.
    """
    if not memo_state:
        return []
    before, after = _board_counts(memo_state), _board_counts(state)
    notes = []
    for name, a in after.items():
        b = before.get(name)
        if not b:
            continue
        who = "us" if a["me"] else name
        if a["lost"] and not b["lost"]:
            notes.append(f"{who} lost the game")
            continue
        dl = a["life"] - b["life"]
        if abs(dl) >= 8:
            notes.append(f"{who}: life {b['life']}→{a['life']} ({dl:+d})")
        spent = len((b["named"] - a["named"]) & ours) if a["me"] else 0
        dn = a["nonland"] - b["nonland"] + spent
        if dn <= -3 or (dn <= -2 and b["nonland"] <= 5) or dn >= 4:
            notes.append(f"{who}: nonland permanents {b['nonland']}→{a['nonland']} ({dn:+d})")
        dc = a["creatures"] - b["creatures"]
        if dc <= -3 or dc >= 4:
            notes.append(f"{who}: creatures {b['creatures']}→{a['creatures']} ({dc:+d})")
        if a["me"]:
            gone = b["named"] - a["named"] - ours
            if gone:
                notes.append("we lost: " + ", ".join(sorted(gone)[:6]))
            cmd = set(state.get("my_command_zone", []))
            if cmd & b["named"] and not cmd & a["named"]:
                notes.append("our commander left the battlefield")
    return notes


# --------------------------------------------------------------------------- pilot

class Pilot:
    def __init__(self, plan: str, strategist: str = "static", log_dir: Path | None = None,
                 model: str = STRATEGIST_MODEL, gate: float = CONFIDENCE_GATE, sync: bool = True,
                 escalate: bool = True, log_state: bool = False, version: str = "v2",
                 deck_path: Path | None = None, effort: str | None = None, verify: str | None = None,
                 every: int = 1, steer: bool = False):
        self.plan = plan
        # Steer mode: Forge's AI keeps the tactics; Jev overrules only where the memo asks for something Forge's
        # answer lacks (see steer_reason). The decision-kind ablations found every kind Jev fully controls
        # costing placement against Forge on the same seeds.
        self.steer = steer
        self.ai_blind = ai_blind_cards(deck_path) if steer else frozenset()
        if deck_path:  # nicknames in memos ("Vivi", "Bolt") must be unambiguous within our deck
            try:
                from .deck import Deck
                set_deck_names(Deck.load(Path(deck_path)).names())
            except Exception:  # noqa: BLE001
                pass
        # Plan at the start of every `every`-th of our turns (and on escalation); memos then cover that many
        # turns, with a NEXT TURNS line for the ones after the first.
        self.every = max(1, every)
        self.strategist = strategist
        self.model = model
        # v2: brief + board names. v3: decklist by zone, card text, dossiers, counted mana, game facts
        # and a memo with a win path and answer earmarks (edhkit/strategist.py).
        self.version = version
        self.effort = effort or ("medium" if version == "v3" else "low")
        self.verify = verify if verify not in (None, "off") and version == "v3" else None  # effort of the check pass
        self._deck = self._db = None
        if version == "v3":
            from .cards import CardDB
            from .deck import Deck
            if not deck_path:
                raise ValueError("strategist v3 needs the deck file")
            self._deck, self._db = Deck.load(deck_path), CardDB()
        self.gate = gate
        self.log_state = log_state or LOG_FULL_STATE
        self.pass_gate = max(gate, PASS_GATE)
        self.sync = sync
        self.escalate = escalate and strategist != "static"
        self.provider = jev.get_provider()
        if isinstance(self.provider, jev.LexicalProvider):
            raise SystemExit("the Jev pilot needs TYPESAFE_API_KEY (in env or .env)")
        self.log_dir = log_dir
        self._log_lock = threading.Lock()
        self._games: dict[str, dict] = {}
        self._glock = threading.Lock()
        self.stats = {"errors": 0, "latency_ms": [], "strategist_calls": 0, "strategist_ms": [],
                      "strategist_errors": 0, "escalations": 0, "escalation_checks": 0,
                      "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}
        self._server: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------------ server
    def start(self) -> str:
        pilot = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                try:
                    out = pilot.ask(body) if self.path == "/ask" else {"ok": True}
                except Exception as e:  # never break the game: empty answers = keep Forge's choices
                    pilot.stats["errors"] += 1
                    print(f"[pilot] error: {e}")
                    out = {"answers": {}}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()

    # ------------------------------------------------------------------ strategist
    def _game(self, game: str) -> dict:
        with self._glock:
            return self._games.setdefault(game, {"memo": "", "memo_state": None, "turn": -1, "pending": False,
                                                 "escalations": 0, "esc_turn": -1, "esc_round": -1, "ours": set(),
                                                 "our_turns": 0, "memo_our_turn": 0})

    def _maybe_turn_refresh(self, game: str, state: dict) -> None:
        """New memo at the first decision of our turn: every turn, or every `every`-th turn (always when there
        is no memo yet)."""
        g = self._game(game)
        turn = state.get("turn", 0)
        with self._glock:
            new_turn = state.get("active") == state.get("me") and g["turn"] != turn and not g["pending"]
            if new_turn:
                g["turn"] = turn
                g["our_turns"] += 1
                g["round_state"] = state  # escalation compares against this once the memo is older
            due = new_turn and self.strategist != "static" and (
                not g["memo"] or g["our_turns"] - g["memo_our_turn"] >= self.every)
            if due:
                g["pending"] = True
        if due:
            reason = "start of our turn" + (f" (plan our next {self.every} turns)" if self.every > 1 else "")
            if self.sync:
                self._refresh(game, state, reason=reason)
            else:
                threading.Thread(target=self._refresh, args=(game, state, reason), daemon=True).start()

    def memo_age(self, g: dict) -> int:
        """How many of our turns ago the memo was written (0: this turn, or since our last turn began)."""
        return g["our_turns"] - g["memo_our_turn"] if g["memo"] else 0

    def _drop_done(self, req: dict, tags: dict) -> dict:
        """Plan-step tags of plays already made under this memo this turn come off: a done "equip Lightning Greaves to
        Vivi" step stayed tagged, and the plan-order rule forced the equip again over Jev's next step (twice in one
        kill turn), as did a flashback recast of a card whose step was done."""
        g = self._game(req.get("game", ""))
        done = g.get("done", {}).get((g["memo"], (req.get("state") or {}).get("turn")), set())
        if not done or "action" not in tags:
            return tags
        q = next((q for q in req.get("questions", []) if q["id"] == "action"), None)
        for o in (q or {}).get("options", []):
            t = tags["action"].get(o["id"], "")
            step, card = re.search(r"THIS TURN plan, step (\d+)", t), _OPTION_CARD.match(o["text"])
            if step and card and (step.group(1), card.group(1)) in done:
                tags["action"][o["id"]] = f" [the memo's step {step.group(1)} for this card was already played this turn]"
        return tags

    def stale(self, age: int) -> bool:
        """A memo older than the strategist's schedule: its refreshes failed. In round 5 of the Vivi runs a spend
        limit failed 42 calls and 26% of decisions ran on memos two or more turns old, whose HOLD lines kept
        declining the plays they named (100 times) and locked a hand for the rest of a game."""
        return age >= max(2, getattr(self, "every", 1))

    def _refresh(self, game: str, state: dict, reason: str, quick: bool = False) -> None:
        """quick: a mid-turn re-plan after a board shock, at low effort and without the verify pass (the game
        waits for it); scheduled plans get the configured effort and the verify pass."""
        g = self._game(game)
        if self.version == "v3":
            from . import strategist
            system = strategist.system_for(self.every)
            prompt = strategist.prompt(self.plan, self._deck, self._db, state, g["memo"], reason)
        else:
            system = STRATEGIST_SYSTEM
            board = json.dumps({k: v for k, v in state.items() if k != "card_text"}, ensure_ascii=False)
            prompt = (f"Deck plan:\n{self.plan}\n\nCurrent board (JSON):\n{board}\n\n"
                      f"Previous memo:\n{g['memo'] or '(none)'}\n\nReason for this memo: {reason}\n\nWrite the new memo.")
        t0 = time.time()
        memo, error = "", None
        try:
            if self.strategist == "claude-cli":
                # Lightweight headless call: neutral cwd (no project CLAUDE.md/skills), no tools,
                # our own system prompt. ~10-15 s at low effort instead of ~2 min for the full harness.
                try:
                    memo = claude_cli.run(system, prompt, self.model, "low" if quick else self.effort)
                except claude_cli.ClaudeCallFailed as e:
                    if quick or "limit" in str(e).lower():  # a spend or session limit won't lift in seconds
                        raise
                    print(f"[pilot] strategist call failed, retrying once: {str(e)[:120]}")
                    time.sleep(STRATEGIST_RETRY_S)
                    memo = claude_cli.run(system, prompt, self.model, self.effort)
                if self.verify and not quick:
                    from . import strategist
                    try:
                        memo = claude_cli.run(strategist.verify_system(self.every), strategist.verify_prompt(prompt, memo),
                                              self.model, self.verify)
                    except claude_cli.ClaudeCallFailed as e:  # keep the unchecked draft
                        self.stats["verify_errors"] = self.stats.get("verify_errors", 0) + 1
                        print(f"[pilot] verify pass failed, keeping the draft memo: {e}")
            elif self.strategist == "anthropic":
                memo = self._anthropic(prompt, system)
        except Exception as e:
            error = str(e)[:200]
            memo = ""
            self.stats["strategist_errors"] += 1
            print(f"[pilot] STRATEGIST FAILED, keeping the previous memo: {error}")
        ms = int((time.time() - t0) * 1000)
        self.stats["strategist_calls"] += 1
        self.stats["strategist_ms"].append(ms)
        with self._glock:
            if memo:
                g["memo"], g["memo_state"] = memo[:3000], state
                g["memo_our_turn"] = g["our_turns"]
                g["ours"] = set()
            g["pending"] = False
        if error:
            self._log({"type": "memo_error", "game": game, "turn": state.get("turn"), "reason": reason,
                       "error": error, "ms": ms})
        else:
            self._log({"type": "memo", "game": game, "turn": state.get("turn"), "reason": reason, "memo": memo,
                       "ms": ms})

    def _anthropic(self, prompt: str, system: str = STRATEGIST_SYSTEM) -> str:
        import anthropic  # optional dependency; only this provider needs it
        client = anthropic.Anthropic()
        # Opus 5.5: thinking is always on and effort defaults to medium, so set effort explicitly.
        resp = client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system,
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    # ------------------------------------------------------------------ executor
    def _jev(self, req: dict, memo: str, changes: list[str], with_escalation: bool,
             age: int = 0) -> tuple[dict, float | None]:
        kind = req.get("kind", "action")
        state = req.get("state", {})
        decision = {"kind": kind, "guidance": KIND_GUIDANCE.get(kind, "")}
        for k in ("window", "stack_top", "cards_to_bottom_if_kept", "incoming", "search"):
            if k in req:
                decision[k] = req[k]
        board = {k: v for k, v in state.items() if k != "card_text"}
        jstate = {"deck_plan": self.plan, "strategy_memo": memo or "(none yet)", "board": board, "decision": decision}
        hazards = feed_hazards(state)
        if hazards:
            jstate["opponent_triggers_our_plays_feed"] = hazards
        if memo and self.stale(age):
            jstate["memo_written"] = (f"{age} of our turns ago, and not refreshed since (the strategist failed): its "
                                      "plan, HOLD and threat lines may no longer fit the board. Judge from the board")
        elif memo and age:
            jstate["memo_written"] = (f"{age} of our turns ago: its THIS TURN is done; follow its NEXT TURNS line "
                                      "for this turn, and its TARGET, THREATS & ANSWERS and HOLD lines as before")
        if state.get("card_text"):
            jstate["card_text"] = state["card_text"]  # oracle text for names on the board, hand and stack
        if changes:
            jstate["changes_since_memo"] = changes
        questions = {}
        order = (threat_order(memo, state) if kind in ("attack", "trigger-target", "action") and not self.stale(age)
                 else [])
        if order:
            jstate["threat_order"] = " > ".join(order) + " (the strategist's ranking of the opponents; see its THREAT ORDER)"
        if kind == "attack":
            jstate["crack_back"] = crack_back(state)
        tags = self._drop_done(req, option_tags(req, memo, age)) if not self.stale(age) else {}
        for q in req.get("questions", []):
            questions[q["id"]] = {"type": "choice",
                                  "instructions": {"question": q["prompt"], "how_to_decide": KIND_GUIDANCE.get(kind, "")},
                                  "criteria": {o["id"]: o["text"] + tags.get(q["id"], {}).get(o["id"], "") for o in q["options"]}}
        if with_escalation:
            questions["__escalate"] = {"type": "noul", "instructions": ESCALATE_QUESTION,
                                       "criteria": {"true": "The memo no longer fits the board; re-plan now",
                                                    "false": "The memo still fits; keep executing it"}}
        answers = self.provider.evaluate(jstate, questions)
        esc = answers.pop("__escalate", {}).get("noul") if with_escalation else None
        return answers, esc

    def _track_life(self, game: str, state: dict) -> None:
        """Life flow per player's turns, from consecutive states: what the other players lost during each player's
        turns and what that player gained. The strategist gets it in OPPONENT STANDING. The memos kept ranking a
        drain deck (Y'shtola, Night's Blessed) last as "slow"; it won 4 of the 6 games watched at its table."""
        g = self._game(game)
        lives = {p["name"]: p.get("life", 0) for p in state.get("players", [])}
        active = state.get("active")
        with self._glock:
            prev = g.get("last_lives")
            flow = g.setdefault("life_flow", {})
            if prev and active:
                f = flow.setdefault(active, {"others_lost": 0, "gained": 0})
                for name, life in lives.items():
                    if name in prev:
                        if name != active and life < prev[name]:
                            f["others_lost"] += prev[name] - life
                        elif name == active and life > prev[name]:
                            f["gained"] += life - prev[name]
            g["last_lives"] = lives
            state["table_pressure"] = {k: dict(v) for k, v in flow.items()}

    def _mulligan_by_strategist(self, req: dict) -> dict | None:
        """Keep or mulligan, decided by the strategist model with the whole hand's text, the deck plan and the table.
        One call per opening hand. In a Vivi game Jev kept Island, Island, Harmonic Prodigy, Wizard's Staff, Mana
        Sculpt, Rhystic Study, Chandra's Ignition (no red source for a commander that needs red) at 0.95; we found red
        on the fourth land drop and lost. Returns None on failure, and the usual executor answers instead."""
        game, state = req.get("game", "?"), req.get("state", {})
        q = next((q for q in req.get("questions", []) if q["id"] == "keep"), None)
        if not q:
            return None
        texts = state.get("card_text", {})
        hand = state.get("my_hand", [])
        me = next((p for p in state.get("players", []) if p.get("is_me")), {})
        others = [f"{p['name']}: {', '.join(p.get('commanders', []))}" for p in state.get("players", []) if not p.get("is_me")]
        prompt = (f"Deck plan:\n{self.plan[:2500]}\n\nOur commander: {', '.join(me.get('commanders', [])) or '?'}"
                  + "".join(f"\n  {c}: {texts[c]}" for c in me.get("commanders", []) if c in texts)
                  + f"\n\nOpponents: {'; '.join(others)}\n\nOpening hand ({len(hand)} cards). "
                  + q["prompt"] + "\n" + "\n".join(f"- {c}: {texts.get(c, '')}" for c in hand)
                  + "\n\nKEEP or MULLIGAN?")
        t0 = time.time()
        try:
            if self.strategist == "claude-cli":
                text = claude_cli.run(MULLIGAN_SYSTEM, prompt, self.model, MULLIGAN_EFFORT)
            elif self.strategist == "anthropic":
                text = self._anthropic(prompt, MULLIGAN_SYSTEM)
            else:
                return None
        except Exception as e:  # noqa: BLE001
            print(f"[pilot] mulligan call failed, the executor decides: {str(e)[:160]}")
            return None
        first = (text.strip().splitlines() or [""])[0].upper()
        choice = "mulligan" if first.startswith("MULLIGAN") else "keep" if first.startswith("KEEP") else None
        if choice is None:
            return None
        ms = int((time.time() - t0) * 1000)
        self.stats["mulligan_calls"] = self.stats.get("mulligan_calls", 0) + 1
        rec = {"type": "decision", "game": game, "turn": state.get("turn"), "phase": state.get("phase"),
               "kind": "mulligan", "ms": ms, "by": "strategist",
               "answers": [{"q": "keep", "default": q.get("default"), "choice": choice, "gated": False,
                            "label": "keep the hand" if choice == "keep" else "mulligan for a new hand",
                            "reason": text.strip()[:600]}]}
        if getattr(self, "log_state", LOG_FULL_STATE):
            rec["state"], rec["memo"], rec["questions"] = state, "", req.get("questions", [])
        self._log(rec)
        return {"answers": {"keep": choice}}

    def ask(self, req: dict) -> dict:
        game = req.get("game", "?")
        kind = req.get("kind", "action")
        state = req.get("state", {})
        if kind == "mulligan" and self.strategist != "static" and MULLIGAN_BY == "strategist":
            decided = self._mulligan_by_strategist(req)
            if decided:
                return decided
        self._track_life(game, state)
        self._maybe_turn_refresh(game, state)
        g = self._game(game)
        # Shocks since the memo, or, once the memo is from an earlier turn of ours, since this round began: a
        # memo meant to last several turns expects the board to develop, and diffing against the board it was
        # written on escalated on ordinary development (26 escalations to 18 scheduled plans in the first K=3 games).
        baseline = g["memo_state"] if not self.memo_age(g) else (g.get("round_state") or g["memo_state"])
        changes = changes_since(baseline, state, g["ours"]) if self.escalate else []
        # At most one escalation per round (our turn to our next): once per game turn allowed up to four a round,
        # and with memos meant to last several turns they fired on most opponents' turns.
        check = bool(self.escalate and g["memo"] and changes and g["escalations"] < MAX_ESCALATIONS_PER_GAME
                     and g["esc_round"] != g["our_turns"])
        t0 = time.time()
        answers, esc = self._jev(req, g["memo"], changes, check, self.memo_age(g))
        escalated = False
        if check:
            self.stats["escalation_checks"] += 1
        if check and esc is not None and esc >= ESCALATE_THRESHOLD:
            escalated = True
            with self._glock:
                g["escalations"] += 1
                g["esc_turn"], g["esc_round"] = state.get("turn"), g["our_turns"]
            self.stats["escalations"] += 1
            self._log({"type": "escalation", "game": game, "turn": state.get("turn"), "kind": kind,
                       "p": round(esc, 3), "changes": changes})
            t_plan = time.time()
            self._refresh(game, state, reason="executor escalation: " + "; ".join(changes), quick=True)
            t0 += time.time() - t_plan  # decision latency excludes the re-plan (counted under strategist_ms)
            answers, _ = self._jev(req, g["memo"], [], False, self.memo_age(g))  # re-ask under the new plan
        ms = int((time.time() - t0) * 1000)
        self.stats["latency_ms"].append(ms)
        ks = self.stats["by_kind"][kind]
        ks["requests"] += 1
        out = {}
        record = []
        # a stale memo informs Jev as context only: no plan, HOLD, keep or threat tags, so no gates follow it
        tag_memo = "" if self.stale(self.memo_age(g)) else g["memo"]
        s_tags = (steer_tags(req, tag_memo, self.memo_age(g), getattr(self, "ai_blind", frozenset()))
                  if getattr(self, "steer", False) else {})
        plan_tags = self._drop_done(req, option_tags(req, tag_memo, self.memo_age(g))) if tag_memo else {}
        for q in req.get("questions", []):
            qid, default = q["id"], q.get("default")
            a = answers.get(qid) or {}
            choice, probs = a.get("choice", default), a.get("probabilities") or {}
            gated = False
            # Vetoing Forge's play ("pass") and overruling its mulligan call need the big margin: every mulligan
            # override in the v2.2 and v3.1 arms (18 of them) went the wrong way. So does sending an attacker Forge
            # keeps home: blind judges preferred Forge's answer in all 8 such overrules audited, and the v3.1
            # post-mortem found them behind several lost games (Muldrotha traded into untapped blockers).
            # Discards too: in all 7 discard overrules of the v3.1 arm Jev threw away mana or a tutor to keep a
            # mid-size creature (the options then showed only card names).
            # And aiming a target at our own card when Forge aims at an opponent's: Grist's -2 on our own permanent
            # lost pod04-g3, and Soul-Guide Lantern exiled our own One Ring from our graveyard in a smoke run.
            opts = {o["id"]: o["text"] for o in q["options"]}
            self_aim = ((kind == "trigger-target" or qid.startswith("tgt_")) and "[ours" in opts.get(choice, "")
                        and "[ours" not in opts.get(default, "[ours"))
            # Attacks need it in both directions. Holding back an attacker Forge sends is the combat form of the
            # pass veto: each hold looked defensible to a blind judge (20-24), but in the K=3 arm Jev held back
            # 1.5 of Forge's 3.2 attacks a game, we dealt 7 combat damage a game to Forge's 17 on the same pods,
            # and finished last in 10 of 24 games.
            a_tags = plan_tags.get(qid, {})
            # Declining a play of a card the memo holds for something else needs only the ordinary margin: Forge spent
            # An Offer You Can't Refuse on a mana rock and Mana Sculpt on Orcish Bowmasters while the memo held them for
            # named threats, and Jev agreed with Forge rather than clear the pass margin.
            held_default = "HOLD" in a_tags.get(default, "")
            # The card's other mode than the memo's (a single-target Cyclonic Rift when the memo overloads it) is a
            # play of the wrong spell: Jev cast the memo's overload Rift single-target in our draw step.
            def memo_mode_on_offer(oid):  # another option for the same card in the memo's mode, or a main phase ahead
                if str(req.get("window", "")).startswith(("our upkeep", "our draw step")):
                    return True  # Vivi's mana for the overload comes in the main phase
                m = _OPTION_CARD.match(next((o["text"] for o in q["options"] if o["id"] == oid), ""))
                return bool(m) and any(o["id"] != oid and o["text"].startswith(f"cast {m.group(1)} (")
                                       and " plan" in a_tags.get(o["id"], "") and not _WRONG_MODE.search(a_tags.get(o["id"], ""))
                                       for o in q["options"])
            if _WRONG_MODE.search(a_tags.get(default, "")) and memo_mode_on_offer(default):
                held_default = True  # declining it needs only the ordinary margin
            # An attack the memo itself orders (or a hold it orders) needs only the ordinary margin: the big margin
            # exists to stop Jev's own tactical overrules, not the plan's.
            memo_attack = kind == "attack" and re.search(r"the memo (?:attacks|keeps this creature home|says no attacks)",
                                                         a_tags.get(choice, ""))
            # Plan order: a later step while an earlier step is on offer needs the big margin, and falls back to the
            # earliest offered step (Jev cast step 2's Rift before step 1's Vivi mana, in the wrong mode, and lost).
            steps = {oid: int(m.group(1)) for oid, t in a_tags.items()
                     if (m := re.search(r"THIS TURN plan, step (\d+)", t))} if (kind == "action" and qid == "action") else {}
            earliest = min(steps, key=steps.get) if steps else None
            jumps = choice in steps and earliest is not None and steps[choice] > steps[earliest]
            big = ((kind == "action" and qid == "action" and choice == "pass" and not held_default)
                   or (kind in ("mulligan", "discard", "attack") and not memo_attack) or self_aim or jumps)
            gate = self.pass_gate if big else self.gate
            # Memo-aligned overrules need only a small margin: the gate handed Jev's pass back to a Chaos Warp the
            # memo held (margin 0.09), and the reveal gave the opponent Bloodline Keeper.
            choice_text = next((o["text"] for o in q["options"] if o["id"] == choice), "")
            planned = " plan" in a_tags.get(choice, "") and "fallback" not in a_tags.get(choice, "")
            if held_default and choice == "pass":
                gate = 0.0
            elif steps and choice in steps and default in steps and steps[choice] < steps[default]:
                gate = 0.0  # Jev keeps the plan's order where Forge would jump ahead (2 reverts in round 6)
            elif (planned and default == "pass"
                  and re.search(r"Forge's AI (?:can't play this card|would not do this now: CantPlayAi)", choice_text)):
                gate = 0.0  # Forge's pass on a card its AI can't play is no judgement (Opt reverted at margin 0.02)
            elif not big and planned and " plan" not in a_tags.get(default, ""):
                gate = min(gate, 0.03)
            raw = choice
            why_back = ""
            if jumps and probs.get(choice, 1.0) - probs.get(earliest, 0.0) < gate:
                choice, gated, why_back = earliest, True, "an earlier plan step is on offer"
            elif choice != default and probs.get(choice, 1.0) - probs.get(default, 0.0) < gate:
                choice, gated = default, True
            # In our own upkeep or draw step, only a play the memo names may overrule Forge's wait: mana spent there
            # is gone in the main phase (Fire Magic in upkeep cost the turn's planned Vivi Ornitier). The same holds
            # while our own spell is on the stack: a response there is for plans that need one.
            if (choice != default and g["memo"] and kind == "action" and qid == "action" and default == "pass"
                    and str(req.get("window", "")).startswith(("our upkeep", "our draw step", "our own spell is on the stack"))
                    and " plan" not in a_tags.get(choice, "")):
                choice, gated, why_back = default, True, "off-plan play in our upkeep or draw step"
            # ... and a planned play there must be one the plan times there, or its first step: all 6 upkeep plays of
            # round 7 jumped main-phase steps (Abrade cast before Niv-Mizzet, which it was meant to follow)
            if (choice != default and kind == "action" and qid == "action" and default == "pass"
                    and str(req.get("window", "")).startswith(("our upkeep", "our draw step"))
                    and " plan" in a_tags.get(choice, "")):
                t = a_tags.get(choice, "")
                quote = re.search(r'plan[^"]*"([^"]*)"', t)
                num = re.search(r"plan, step (\d+)", t)
                if not ((quote and re.search(r"\b(?:upkeep|draw step|in response|respond)", quote.group(1), re.I))
                        or (num and num.group(1) == "1")):
                    choice, gated, why_back = default, True, "the plan plays this card in the main phase"
            # With our own spell on the stack, a planned play answers it only if its step names that spell: a later
            # step was cast in response to the earlier one (Opt over Hexing Squelcher, which then never protected
            # the storm turn; P4 survived at 4 and killed us)
            if (choice != default and kind == "action" and qid == "action" and default == "pass"
                    and str(req.get("window", "")).startswith("our own spell is on the stack")):
                top = re.split(r" - | \(", str(req.get("stack_top", "")), maxsplit=1)[0].strip()
                quote = re.search(r'plan[^"]*"([^"]*)"', a_tags.get(choice, ""))
                if top and not (quote and any(re.search(rf"\b{re.escape(a)}\b", quote.group(1), re.I)
                                              for a in _aliases(top))):
                    choice, gated, why_back = default, True, f"its plan step doesn't respond to our {top} on the stack"
            # Two overruling equips per equipment per turn (a move and a move back): the plan step "equip Lightning
            # Greaves to Vivi" stays tagged after it's done, and Jev moved Greaves between two creatures 17 times in one
            # main phase. One was too few: moving Greaves off Vivi to aim an Aura at her and back is a real line.
            eq = _EQUIP.match(next((o["text"] for o in q["options"] if o["id"] == choice), "")) if kind == "action" else None
            if eq and choice != default:
                key = (state.get("turn"), eq.group(1))
                if g.setdefault("equips", {}).get(key, 0) >= 2:
                    choice, gated, why_back = default, True, "equipment already moved twice this turn"
                else:
                    g["equips"][key] = g["equips"].get(key, 0) + 1
            if (kind == "action" and qid == "action" and _WRONG_MODE.search(a_tags.get(choice, ""))
                    and memo_mode_on_offer(choice) and any(o["id"] == "pass" for o in q["options"])):
                choice, gated, why_back = "pass", True, "the memo plays this card in its other mode"
            if kind == "block" and choice == "none" and default != "none" and block_lethal(req):
                choice, gated, why_back = default, True, "not blocking a lethal attack"
            # A card the memo keeps is not what we put back or discard while something else can go (Jev discarded
            # Lightning Greaves over a Mountain, and put back Windfall, the lethal turn's step 3).
            # Not when Jev picked what Forge picked: the tag, not the pick, is then the likelier mistake.
            if kind in ("search", "discard") and choice != default and "keep it in hand" in a_tags.get(choice, ""):
                free = [o["id"] for o in q["options"] if "keep it in hand" not in a_tags.get(o["id"], "")
                        and o["id"] != "none"]
                if free:
                    choice, gated, why_back = (default if default in free else max(free, key=lambda o: probs.get(o, 0))), \
                        True, "the memo keeps this card"
            # On an opponent's turn, an answer the HOLD reserves for a named threat waits for that threat (Arcane
            # Denial went on Edgar Markov while the HOLD kept it for Sephiroth, who then resolved uncontested).
            reserved = re.search(r'HOLD[^"]*"([^"]*)"', a_tags.get(choice, "")) if kind == "action" else None
            if (reserved and choice != "pass" and str(req.get("window", "")).startswith("responding to an opponent")
                    and any(o["id"] == "pass" for o in q["options"])):
                # the threats it waits for: every "for X" but the card itself or another card of ours ("keep two blue
                # untapped for Negate" named Negate, and the veto held Negate back from Sanguine Bond, which killed us)
                own = _OPTION_CARD.match(next((o["text"] for o in q["options"] if o["id"] == choice), ""))
                own = own.group(1) if own else ""
                wanted = [w for w in re.findall(r"\bfor ([A-Z][\w',-]+(?: [A-Z][\w',-]+)*)", reserved.group(1))
                          if not own.startswith(w.split(",")[0]) and w.split(",")[0] not in own
                          and not any(n.startswith(w.split(",")[0]) for n in _DECK_NAMES)]
                top = str(req.get("stack_top", ""))
                if wanted and not any(w.split(",")[0] in top for w in wanted):
                    choice, gated, why_back = "pass", True, f"the HOLD reserves this card for {wanted[0]}"
            if (kind == "action" and qid == "action" and choice != "pass"
                    and "THE TARGET CAN'T BE COUNTERED" in next((o["text"] for o in q["options"] if o["id"] == choice), "")
                    and any(o["id"] == "pass" for o in q["options"])):
                choice, gated, why_back = "pass", True, "the counterspell's target can't be countered"
            # Library guard: with a draw engine on damage to opponents (Tandem Lookout pairs, Ophidian Eye), pinging
            # an opponent draws; near an empty library the chain decked us after the memo said to stop at 12 cards.
            me_lib = next((p.get("library_size") for p in state.get("players", []) if p.get("is_me")), None)
            if me_lib is not None and me_lib <= LIBRARY_FLOOR and _draw_on_damage(state):
                opts_q = {o["id"]: o["text"] for o in q["options"]}
                if kind == "trigger-target" and re.match(r"^P\d \(", opts_q.get(choice, "")):
                    life = re.match(r"^P\d \((-?\d+) life", opts_q.get(choice, ""))
                    others = [o for o, t in opts_q.items() if not re.match(r"^(P\d|us) \(", t) and o != "none"]
                    alive = [p for p in state.get("players", []) if not p.get("is_me") and not p.get("lost")]
                    # the last opponent standing dies before the library runs out: each ping but the last draws one
                    wins = life and len(alive) == 1 and int(life.group(1)) <= me_lib
                    if others and not (life and int(life.group(1)) <= 1) and not wins:
                        theirs = [o for o in others if "[ours" not in opts_q[o]]
                        choice, gated, why_back = (theirs or others)[0], True, f"our library has {me_lib} cards"
                if (kind == "optional-trigger" and me_lib <= 3 and choice == "yes"
                        and re.search(r"\bdraw", " ".join(x.get("prompt", "") for x in req.get("questions", [])), re.I)):
                    choice, gated, why_back = "no", True, f"our library has {me_lib} cards"
            # Mana the hand can't spend: the option says so (Vivi made 12 mana with only a counterspell in hand).
            if (kind == "action" and qid == "action" and choice != default
                    and "NOTHING in hand needs this mana now" in next((o["text"] for o in q["options"] if o["id"] == choice), "")):
                choice, gated, why_back = default, True, "mana with nothing to spend it on"
            steered = ""
            if getattr(self, "steer", False) and choice != default:
                steered = steer_reason(kind, qid, choice, default, s_tags.get(qid, {}))
                if not steered:  # steer mode: Forge keeps every call the memo doesn't ask to change
                    choice, gated = default, True
            out[qid] = choice
            if kind == "action" and qid == "action" and choice != "pass":  # this step is being played now
                step = re.search(r"THIS TURN plan, step (\d+)", a_tags.get(choice, ""))
                card = _OPTION_CARD.match(next((o["text"] for o in q["options"] if o["id"] == choice), ""))
                if step and card:
                    g.setdefault("done", {}).setdefault((g["memo"], state.get("turn")), set()).add(
                        (step.group(1), card.group(1)))
            label = next((o["text"] for o in q["options"] if o["id"] == choice), choice)
            rec = {"q": qid, "default": default, "choice": choice, "gated": gated,
                   "label": label[:90], "p": round(probs.get(choice, 0), 3)}
            if choice != default or gated:
                rec["default_label"] = next((o["text"] for o in q["options"] if o["id"] == default), default)[:90]
                rec["p_default"] = round(probs.get(default, 0), 3)
            if steered:
                rec["steer"] = steered
            if why_back:
                rec["back_to_forge"] = why_back
            if gated:  # what Jev wanted, so sub-margin preferences can be audited later
                rec["raw_choice"] = raw
                rec["raw_label"] = next((o["text"] for o in q["options"] if o["id"] == raw), raw)[:90]
                rec["margin"] = round(probs.get(raw, 0) - probs.get(default, 0), 3)
            if kind in ("search", "mulligan") or len(q["options"]) <= 3:
                rec["n_options"] = len(q["options"])
            if kind == "action" and qid == "action":  # which options the memo's plan / HOLD named, for audits
                offered = frozenset(m.group(1) for o in q["options"] if (m := _OPTION_CARD.match(o["text"])))
                tags = {o["id"]: plan_marker(g["memo"], o["text"], self.memo_age(g) == 0, offered)
                        for o in q["options"]}
                planned = [k for k, t in tags.items() if " plan" in t]
                held = [k for k, t in tags.items() if "HOLD" in t]
                if planned:
                    rec["plan_marked"] = planned
                if held:
                    rec["hold_marked"] = held
            record.append(rec)
        self._note_spent(g, kind, req, out)
        # Speculative target and X questions only matter for the action actually taken.
        taken = out.get("action", "") if kind == "action" else None
        for r in record:
            if taken is not None and r["q"].startswith(("tgt_", "x_")) and r["q"].split("_", 1)[1] != taken:
                r["unused"] = True
                continue
            ks["questions"] += 1
            ks["overrules"] += r["choice"] != r["default"]
            ks["gated"] += r["gated"]
        aims = kind in ("attack", "trigger-target") or any(q["id"].startswith("tgt_") for q in req.get("questions", []))
        order = threat_order(g["memo"], state) if aims else []
        rec = {"type": "decision", "game": game, "turn": state.get("turn"), "phase": state.get("phase"),
               "kind": kind, "ms": ms, "escalated": escalated, "memo_age": self.memo_age(g),
               **({"threat_order": order} if order else {}),
               "esc_p": None if esc is None else round(esc, 3), "answers": record}
        if getattr(self, "log_state", LOG_FULL_STATE):  # for offline audits of single decisions (~10x bigger logs)
            rec["state"] = state
            rec["memo"] = g["memo"]
            rec["questions"] = req.get("questions", [])
            rec["context"] = {k: req[k] for k in ("window", "stack_top", "incoming", "search", "scan_truncated")
                              if k in req}
        self._log(rec)
        return {"answers": out}

    _SELF_SAC = re.compile(r"^activate (?P<name>.+?) \(from Battlefield\): (?P<body>.*)$")

    def _note_spent(self, g: dict, kind: str, req: dict, out: dict) -> None:
        """Remember permanents we are about to use up on purpose, so their loss isn't escalated."""
        qs = {q["id"]: q for q in req.get("questions", [])}
        if kind == "action" and "action" in qs:
            text = next((o["text"] for o in qs["action"]["options"] if o["id"] == out.get("action")), "")
            m = self._SELF_SAC.match(text)
            if m and re.search(r"[Ss]acrifice (?:" + re.escape(m["name"]) + r"|~|this)", m["body"]):
                g["ours"].add(m["name"])
        elif kind == "sacrifice-cost" and "pick" in qs:
            text = next((o["text"] for o in qs["pick"]["options"] if o["id"] == out.get("pick")), "")
            if text:
                g["ours"].add(text.split(" [")[0])

    # ------------------------------------------------------------------ bookkeeping
    def _log(self, rec: dict) -> None:
        if not self.log_dir:
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with self._log_lock, open(self.log_dir / "pilot_decisions.jsonl", "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        s = self.stats
        lat = sorted(s["latency_ms"])
        usage = getattr(self.provider, "usage", {})
        tokens = usage.get("input_tokens", 0)
        by_kind = {k: dict(v) for k, v in s["by_kind"].items()}
        questions = sum(v["questions"] for v in by_kind.values())
        overrules = sum(v["overrules"] for v in by_kind.values())
        return {
            "strategist": self.strategist, "strategist_model": self.model if self.strategist != "static" else None,
            "requests": sum(v["requests"] for v in by_kind.values()), "questions": questions, "errors": s["errors"],
            "overrule_rate": round(overrules / questions, 3) if questions else 0,
            "by_kind": by_kind,
            "latency_ms_avg": int(mean(lat)) if lat else None,
            "latency_ms_p95": lat[int(len(lat) * 0.95)] if lat else None,
            "jev_input_tokens": tokens, "jev_usd": round(tokens / 1e6 * jev.PRICE_PER_MTOK, 4),
            "strategist_calls": s["strategist_calls"], "strategist_errors": s["strategist_errors"],
            "strategist_ms_avg": int(mean(s["strategist_ms"])) if s["strategist_ms"] else None,
            "escalation_checks": s["escalation_checks"], "escalations": s["escalations"],
        }
