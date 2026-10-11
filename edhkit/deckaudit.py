"""Audits for a drafted deck: what it left out, whether its notes are true, and whether its gems earn the slot.

- omissions: EDHREC staples for this commander that the list doesn't run, and whether the notes say why.
  Building from the brief up is what makes the decks distinct; this is the check that the distinctiveness
  was chosen rather than stumbled into.
- claims: every `# role: why` annotation, and every notes.md line that names two or more of the deck's cards,
  checked against the oracle text by a separate model call that sees only card text. Misread cards
  ("near-one-sided", the wrong player gets the Treasures, ward paid by the wrong side) are the commonest
  failure in this repo's history; a checker with nothing but the text catches most of them.
- gems: each `GEM vs <Staple>` judged blind against the staple it displaced, in random order, given the brief
  and the deck but not the builder's argument. A hit rate makes taste comparable across builder versions.
  It does not validate taste in absolute terms: a model judging a model's picks shares its blind spots.
"""
from __future__ import annotations

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cards import Card, CardDB
from .deck import Deck, Entry

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
JUDGE_MODEL = "claude-opus-5-5"


# --------------------------------------------------------------------------- helpers

def _short_names(card: Card) -> set[str]:
    """How a note may refer to a card: full name, front face, and the part before a comma ("Muldrotha")."""
    out = {card.name, card.front_name}
    head = card.front_name.split(",")[0].strip()
    if len(head) >= 5:
        out.add(head)
    return {n for n in out if n}


def mentioned(text: str, deck_cards: list[Card], exclude: str | None = None) -> list[Card]:
    found = []
    for c in deck_cards:
        if c.name == exclude:
            continue
        if any(re.search(r"(?<![\w'])" + re.escape(n) + r"(?![\w'])", text) for n in _short_names(c)):
            found.append(c)
    return found


def _json_list(text: str) -> list:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        v = json.loads(m.group(0))
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


def _call(system: str, prompt: str, model: str, effort: str) -> str:
    from .claude_cli import ClaudeCallFailed, run
    try:
        return run(system, prompt, model, effort, timeout=900)
    except ClaudeCallFailed as e:
        return f"CALL FAILED: {e}"


def _card_text(c: Card) -> str:
    return f"{c.name} {c.mana_cost} — {c.type_line}{(' ' + c.pt) if c.pt else ''}\n{c.text}"


# --------------------------------------------------------------------------- omissions

def omissions(deck: Deck, notes: str, bracket: int | None, min_inclusion: float = 0.4) -> list[dict]:
    from . import edhrec
    page = edhrec.commander_page([e.name for e in deck.commanders], bracket)
    names = deck.names()
    deck_text = notes + "\n" + "\n".join(e.note for e in deck.main + deck.maybe)
    maybe = {e.name for e in deck.maybe}
    out = []
    for name, v in sorted(page.get("cards", {}).items(), key=lambda kv: -(kv[1].get("inclusion") or 0)):
        inc = v.get("inclusion") or 0
        if inc < min_inclusion or name in BASICS or name in names:
            continue
        said = name in maybe or re.search(r"(?<![\w'])" + re.escape(name.split(" // ")[0]) + r"(?![\w'])", deck_text)
        out.append({"name": name, "inclusion": inc, "synergy": v.get("synergy"), "addressed": bool(said)})
    return out


def omissions_report(rows: list[dict]) -> str:
    if not rows:
        return "No high-inclusion staples omitted."
    todo = [r for r in rows if not r["addressed"]]
    L = [f"{len(rows)} high-inclusion staples not in the list; {len(todo)} not mentioned in notes.md or the maybeboard:"]
    for r in rows:
        mark = "ok " if r["addressed"] else "!! "
        L.append(f"  {mark}{r['inclusion']:.0%}  {r['name']}" + (f"  (synergy {r['synergy']:+.2f})" if r.get("synergy") is not None else ""))
    if todo:
        L.append("For each '!!': add a line to notes.md (Omitted staples) saying why it's out, or what replaced it.")
    return "\n".join(L)


# --------------------------------------------------------------------------- claims

CLAIMS_SYSTEM = (
    "You are a Magic: The Gathering rules expert checking a Commander deck's notes for factual accuracy. "
    "Each item is a claim a deckbuilder wrote about a card or an interaction. You are given the exact oracle "
    "text of every card involved. Judge only whether the claim is TRUE as written under the comprehensive "
    "rules and the oracle text: who controls or pays what, whose permanents are affected, timing and speed, "
    "targeting, 'may' versus mandatory, zones, replacement versus trigger, legend rule, how the commander "
    "interacts. Do not judge strategy, card quality or whether the card belongs in the deck.\n\n"
    "Reply with only a JSON array, one object per item, in order:\n"
    '[{"id": n, "verdict": "ok" | "wrong" | "overstated" | "unclear", "issue": "<= 40 words, empty if ok", '
    '"fix": "corrected wording, empty if ok"}]\n'
    "'wrong': the claim is false. 'overstated': true only with an unstated condition, or the effect is smaller "
    "than claimed. 'unclear': the claim is too vague to check. Be strict about asymmetry claims "
    "('one-sided', 'only opponents', 'spares us') and about anything stated as automatic or free."
)


def claim_items(deck: Deck, notes: str, max_note_lines: int = 40) -> list[dict]:
    deck_cards = [e.card for e in deck.commanders + deck.main if e.card]
    items = []
    for e in deck.main:
        if not e.card or not e.note or e.card.is_land and not e.note:
            continue
        refs = mentioned(e.note, deck_cards, exclude=e.card.name)
        items.append({"source": "deck.txt", "card": e.card.name, "claim": f"{e.card.name}: {e.note}",
                      "cards": [e.card.name] + [c.name for c in refs]})
    n = 0
    for raw in notes.splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip()
        if len(line) < 25:
            continue
        refs = mentioned(line, deck_cards)
        if len(refs) >= 2:
            items.append({"source": "notes.md", "card": None, "claim": line[:600], "cards": [c.name for c in refs][:6]})
            n += 1
            if n >= max_note_lines:
                break
    return items


def audit_claims(deck: Deck, notes: str, db: CardDB, model: str = JUDGE_MODEL, effort: str = "medium",
                 batch: int = 12, workers: int = 4) -> list[dict]:
    items = claim_items(deck, notes)
    commander = [e.card for e in deck.commanders if e.card]
    batches = [items[i:i + batch] for i in range(0, len(items), batch)]

    def run(b: list[dict]) -> list[dict]:
        names = []
        for it in b:
            for nm in it["cards"]:
                if nm not in names:
                    names.append(nm)
        texts = [_card_text(c) for c in commander] + [_card_text(db.require(nm)) for nm in names]
        lines = [f'{k}. [{it["source"]}] {it["claim"]}' for k, it in enumerate(b, 1)]
        prompt = ("COMMANDER AND CARDS (oracle text):\n\n" + "\n\n".join(texts)
                  + "\n\nCLAIMS:\n" + "\n".join(lines) + "\n\nCheck each claim.")
        reply = _call(CLAIMS_SYSTEM, prompt, model, effort)
        verdicts = {int(v.get("id", 0)): v for v in _json_list(reply) if isinstance(v, dict)}
        out = []
        for k, it in enumerate(b, 1):
            v = verdicts.get(k, {})
            out.append({**it, "verdict": v.get("verdict", "unparsed" if not reply.startswith("CALL FAILED") else "failed"),
                        "issue": v.get("issue", reply[:200] if not v else ""), "fix": v.get("fix", "")})
        return out

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [r for chunk in ex.map(run, batches) for r in chunk]


def claims_report(rows: list[dict]) -> str:
    from collections import Counter
    c = Counter(r["verdict"] for r in rows)
    L = [f"{len(rows)} claims checked: " + ", ".join(f"{k} {v}" for k, v in c.most_common())]
    for r in rows:
        if r["verdict"] != "ok":
            L.append(f"  [{r['verdict']}] ({r['source']}) {r['claim'][:160]}")
            if r.get("issue"):
                L.append(f"      issue: {r['issue']}")
            if r.get("fix"):
                L.append(f"      fix:   {r['fix']}")
    return "\n".join(L)


# --------------------------------------------------------------------------- gems

VS = re.compile(r"\bvs\.?\s+([A-Z][^:;,()\n]*?)(?=\s*[:;,()]|\s+—|\s+-\s|$)")

GEMS_SYSTEM = (
    "You are a world-class Commander player choosing between two cards for one slot in a specific deck. For "
    "each pair, decide which card does more for THIS deck's plan at its bracket, in the role named, given the "
    "rest of the list. Consider synergy with the commander and the deck, mana cost and timing, how often it is "
    "live, and what it does when drawn late or early. Fame is irrelevant and so is price (every card is a "
    "proxy). Reply with only a JSON array, one object per pair, in order:\n"
    '[{"id": n, "pick": "A" | "B" | "SAME", "margin": "slight" | "clear" | "decisive" | null, '
    '"reason": "<= 30 words"}]'
)


def gem_entries(deck: Deck) -> list[tuple[Entry, str | None, str]]:
    """(entry, staple named after 'vs', role label) for every GEM-marked card."""
    out = []
    for e in deck.main:
        if not e.note or not re.search(r"\bGEM\b", e.note):
            continue
        m = VS.search(e.note)
        staple = m.group(1).strip() if m else None
        head = e.note.split(":")[0]
        if m:
            head = head.replace(m.group(0), "")
        role = re.sub(r"\bGEM\b", "", head).strip(" -—") or "plan"
        out.append((e, staple, role))
    return out


def audit_gems(deck: Deck, brief: str, db: CardDB, model: str = JUDGE_MODEL, effort: str = "medium",
               batch: int = 8, seed: int = 7, workers: int = 4, both_orders: bool = True) -> list[dict]:
    """Judge each named gem against its staple. With both_orders (default), every pair is judged twice, once
    in each A/B position, in separate calls: a verdict counts only if it survives the swap, else it's 'split'.
    A single run flipped five of eighteen verdicts between identical re-runs on the Obeka build."""
    rng = random.Random(seed)
    names = deck.names()
    rows, pairs = [], []
    for e, staple, role in gem_entries(deck):
        row = {"gem": e.name, "staple": staple, "role": role, "votes": []}
        if not staple:
            row["result"] = "no staple named"
        else:
            try:
                sc = db.require(staple)
            except KeyError:
                row["result"] = f"staple not found: {staple}"
                sc = None
            if sc is not None and sc.name in names:
                row["result"] = "staple is also in the deck (not displaced)"
            elif sc is not None:
                row["staple"] = sc.name
                first = rng.random() < 0.5
                pairs.append((row, e.card, sc, first))
                if both_orders:
                    pairs.append((row, e.card, sc, not first))
        rows.append(row)
    commander = [e.card for e in deck.commanders if e.card]
    deck_list = ", ".join(sorted(n for n in names if n not in BASICS))
    # the two orderings of a pair always go in different calls
    groups = [pairs[0::2], pairs[1::2]] if both_orders else [pairs]
    chunks = [g[i:i + batch] for g in groups for i in range(0, len(g), batch)]

    def run(chunk):
        lines = []
        for k, (row, gem, staple, gem_first) in enumerate(chunk, 1):
            a, b = (gem, staple) if gem_first else (staple, gem)
            lines.append(f"PAIR {k} (role: {row['role']})\n  A: {_card_text(a)}\n  B: {_card_text(b)}")
        prompt = (f"DECK PLAN:\n{brief[:3000]}\n\nCOMMANDER:\n" + "\n".join(_card_text(c) for c in commander)
                  + f"\n\nTHE REST OF THE LIST:\n{deck_list}\n\n" + "\n\n".join(lines) + "\n\nChoose for each pair.")
        reply = _call(GEMS_SYSTEM, prompt, model, effort)
        verdicts = {int(v.get("id", 0)): v for v in _json_list(reply) if isinstance(v, dict)}
        for k, (row, gem, staple, gem_first) in enumerate(chunk, 1):
            v = verdicts.get(k)
            if not v:
                row["votes"].append({"vote": "unparsed"})
                continue
            pick = str(v.get("pick", "")).upper()
            vote = "same" if pick == "SAME" else "gem better" if (pick == "A") == gem_first else "staple better"
            row["votes"].append({"vote": vote, "margin": v.get("margin"), "reason": v.get("reason")})

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(run, chunks))
    for row in rows:
        votes = [v["vote"] for v in row["votes"] if v["vote"] != "unparsed"]
        if "result" in row:
            continue
        if not votes:
            row["result"] = "unparsed"
        elif len(set(votes)) == 1:
            row["result"] = votes[0]
        elif set(votes) == {"same", "gem better"}:
            row["result"] = "same"
        elif set(votes) == {"same", "staple better"}:
            row["result"] = "staple better"
        else:
            row["result"] = "split"
        last = next((v for v in row["votes"] if v.get("reason")), {})
        row["margin"], row["reason"] = last.get("margin"), last.get("reason")
    return rows


def gems_report(rows: list[dict]) -> str:
    from collections import Counter
    c = Counter(r.get("result") for r in rows)
    judged = c["gem better"] + c["staple better"] + c["same"] + c["split"]
    L = [f"{len(rows)} GEMs: " + ", ".join(f"{k} {v}" for k, v in c.most_common())]
    if judged:
        L.append(f"hit rate (gem better or same, in both A/B orders): {(c['gem better'] + c['same']) / judged:.0%} "
                 f"of {judged} judged; {c['split']} split (the verdict flipped with the order: treat as a coin flip)")
    for r in rows:
        res = r.get("result")
        if res != "gem better":
            extra = f" ({r.get('margin')}) {r.get('reason') or ''}" if res in ("staple better", "same", "split") else ""
            L.append(f"  [{res}] {r['gem']} vs {r.get('staple') or '?'}{extra}")
    return "\n".join(L)


def save(rows, deck_file: str, name: str) -> Path:
    out = Path(deck_file).resolve().parent / "audit" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    return out
