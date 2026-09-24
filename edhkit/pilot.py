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
              "memo's HOLD names or that answers a likely threat on opponents' turns; holding costs this turn's plays.",
    "attack": "We are declaring attackers. For this creature, decide whether and whom to attack. Each option says "
              "how Forge's combat rules see it (which blockers could kill it). Weigh the defending player's untapped "
              "blockers, whether we need it back as a blocker, the memo's threats, and any chance to finish a player. "
              "Our commander and the engine pieces the plan names are worth far more than their combat damage: don't "
              "send them where a block can kill them unless the attack wins the game or the memo says to.",
    "block": "An opponent is attacking. Pick a blocker for this attacker or none. Protect engine pieces named "
             "in the plan/memo unless the damage is dangerous; prefer blocks that kill the attacker and survive; "
             "chump only when the damage matters.",
    "mulligan": "Opening hand decision. Count lands from the question (and my_hand_summary), not from card "
                "names. A 7-card hand with 0 or 1 land is a mulligan; 2 lands only with cheap ramp or card draw; "
                "3-5 lands with plays by turn 3-4 is a keep; 6+ lands is usually a mulligan. Our commander costs a "
                "lot, so land drops matter more than any single spell.",
    "confirm": "An optional effect asks yes or no. Say yes when it advances our plan at acceptable cost.",
    "choose": "An effect asks us to choose one. Pick what best serves our plan or hurts the biggest threat.",
    "sacrifice": "We must sacrifice a permanent. Lose what hurts the plan least: tokens, spent permanents, or "
                 "cards our recursion can bring back.",
    "sacrifice-cost": "We are paying a sacrifice cost. Sacrifice what hurts the plan least: tokens, spent "
                      "permanents, or cards our recursion can replay; never a key engine piece unless the plan says so.",
    "surveil": "Surveil: keep on top what we want to draw next; put into the graveyard what our graveyard "
               "plan can use or what we don't need.",
    "scry": "Scry: keep on top what we want to draw next; bottom the rest.",
    "trigger-target": "Choose the target for our triggered ability. Aim harmful effects at opponents' best "
                      "threats (the memo's top threat first) and beneficial ones at our own key permanents.",
    "optional-trigger": "One of our 'you may' triggers is resolving. Say yes when it helps our plan now; no when "
                        "it would hurt us (e.g. a cost we can't afford, a symmetric effect that helps opponents more).",
    "search": "We are searching a zone and take one card (a tutor, fetch land, ramp spell or recursion). Take "
              "the card that most advances the memo's plan from this board (a named tutor target first): the "
              "missing engine piece, the answer to the current top threat, or the land that fixes what our hand needs. Read each land's type "
              "line: a dual or tri land with the searched basic land type makes more colors than the basic and "
              "is usually the better fetch.",
    "discard": "We must discard one card. With a graveyard plan, discarding a card we can recast or replay from "
               "the graveyard is nearly free; otherwise discard what is least useful from this board state.",
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
                    r"(?: \{.*\})?(?: x(?P<n>\d+))?(?: \(tapped \d+\))?$")


def parse_entry(entry: str) -> dict:
    m = _ENTRY.match(entry)
    if not m:
        return {"name": entry, "n": 1, "creature": False, "token": False, "land": False}
    return {"name": m["name"], "n": int(m["n"] or 1), "creature": bool(m["pt"]),
            "token": bool(m["token"]), "land": bool(m["land"])}


_MEMO_HEAD = re.compile(r"^(THIS TURN|TARGET|WIN PATH|THREATS & ANSWERS|HOLD|REPLAN IF|PRIORITIES|THREAT)\b[^:\n]*:?", re.M)
_OPTION_CARD = re.compile(r"^(?:cast|activate|play land) (.+?) \(from ")


@functools.lru_cache(maxsize=64)
def memo_sections(memo: str) -> dict:
    """The memo's labelled lines (THIS TURN, HOLD, ...) by label."""
    heads = list(_MEMO_HEAD.finditer(memo or ""))
    return {m.group(1): memo[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(memo)]
            for i, m in enumerate(heads)}


def _find_card(text: str, name: str) -> int:
    if name in text:
        return text.index(name)
    short = name.split(" // ")[0].split(",")[0]
    m = re.search(r"\b" + re.escape(short) + r"\b", text) if len(short) > 5 else None
    return m.start() if m else -1


def plan_marker(memo: str, option_text: str) -> str:
    """Tag for an action option whose card the memo's THIS TURN plan or HOLD line names.

    Jev reads the whole memo, but matching card names across 20-odd options is where it slips: in the v3.1
    post-mortem the most common game-losing mistake was a planned play left unmade while it was on offer.
    """
    m = _OPTION_CARD.match(option_text)
    if not m or not memo:
        return ""
    name, secs, tags = m.group(1), memo_sections(memo), []
    plan = secs.get("THIS TURN") or secs.get("PRIORITIES") or ""
    at = _find_card(plan, name)
    if at >= 0:
        steps = re.findall(r"(?:^|\s)(\d+)[).]\s", plan[:at + 1])
        tags.append("named in the memo's THIS TURN plan" + (f", step {steps[-1]}" if steps else ""))
    if _find_card(secs.get("HOLD", ""), name) >= 0:
        tags.append("named in the memo's HOLD line")
    return f" [{'; '.join(tags)}]" if tags else ""


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
                 deck_path: Path | None = None, effort: str | None = None, verify: str | None = None):
        self.plan = plan
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
                                                 "escalations": 0, "esc_turn": -1, "ours": set()})

    def _maybe_turn_refresh(self, game: str, state: dict) -> None:
        """New memo at the first decision of each of our turns."""
        if self.strategist == "static":
            return
        g = self._game(game)
        turn = state.get("turn", 0)
        with self._glock:
            start = state.get("active") == state.get("me") and g["turn"] != turn and not g["pending"]
            if start:
                g["pending"], g["turn"] = True, turn
        if start:
            if self.sync:
                self._refresh(game, state, reason="start of our turn")
            else:
                threading.Thread(target=self._refresh, args=(game, state, "start of our turn"), daemon=True).start()

    def _refresh(self, game: str, state: dict, reason: str) -> None:
        g = self._game(game)
        if self.version == "v3":
            from . import strategist
            system = strategist.SYSTEM
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
                memo = claude_cli.run(system, prompt, self.model, self.effort)
                if self.verify:
                    from . import strategist
                    try:
                        memo = claude_cli.run(strategist.VERIFY_SYSTEM, strategist.verify_prompt(prompt, memo),
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
                g["memo"], g["memo_state"] = memo[:2000], state
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
    def _jev(self, req: dict, memo: str, changes: list[str], with_escalation: bool) -> tuple[dict, float | None]:
        kind = req.get("kind", "action")
        state = req.get("state", {})
        decision = {"kind": kind, "guidance": KIND_GUIDANCE.get(kind, "")}
        for k in ("window", "stack_top", "cards_to_bottom_if_kept"):
            if k in req:
                decision[k] = req[k]
        board = {k: v for k, v in state.items() if k != "card_text"}
        jstate = {"deck_plan": self.plan, "strategy_memo": memo or "(none yet)", "board": board, "decision": decision}
        if state.get("card_text"):
            jstate["card_text"] = state["card_text"]  # oracle text for names on the board, hand and stack
        if changes:
            jstate["changes_since_memo"] = changes
        questions = {}
        for q in req.get("questions", []):
            mark = kind == "action" and q["id"] == "action"
            questions[q["id"]] = {"type": "choice",
                                  "instructions": {"question": q["prompt"], "how_to_decide": KIND_GUIDANCE.get(kind, "")},
                                  "criteria": {o["id"]: o["text"] + (plan_marker(memo, o["text"]) if mark else "")
                                               for o in q["options"]}}
        if with_escalation:
            questions["__escalate"] = {"type": "noul", "instructions": ESCALATE_QUESTION,
                                       "criteria": {"true": "The memo no longer fits the board; re-plan now",
                                                    "false": "The memo still fits; keep executing it"}}
        answers = self.provider.evaluate(jstate, questions)
        esc = answers.pop("__escalate", {}).get("noul") if with_escalation else None
        return answers, esc

    def ask(self, req: dict) -> dict:
        game = req.get("game", "?")
        kind = req.get("kind", "action")
        state = req.get("state", {})
        self._maybe_turn_refresh(game, state)
        g = self._game(game)
        changes = changes_since(g["memo_state"], state, g["ours"]) if self.escalate else []
        check = bool(self.escalate and g["memo"] and changes and g["escalations"] < MAX_ESCALATIONS_PER_GAME
                     and g["esc_turn"] != state.get("turn"))
        t0 = time.time()
        answers, esc = self._jev(req, g["memo"], changes, check)
        escalated = False
        if check:
            self.stats["escalation_checks"] += 1
        if check and esc is not None and esc >= ESCALATE_THRESHOLD:
            escalated = True
            with self._glock:
                g["escalations"] += 1
                g["esc_turn"] = state.get("turn")
            self.stats["escalations"] += 1
            self._log({"type": "escalation", "game": game, "turn": state.get("turn"), "kind": kind,
                       "p": round(esc, 3), "changes": changes})
            t_plan = time.time()
            self._refresh(game, state, reason="executor escalation: " + "; ".join(changes))
            t0 += time.time() - t_plan  # decision latency excludes the re-plan (counted under strategist_ms)
            answers, _ = self._jev(req, g["memo"], [], False)  # re-ask this decision under the new plan
        ms = int((time.time() - t0) * 1000)
        self.stats["latency_ms"].append(ms)
        ks = self.stats["by_kind"][kind]
        ks["requests"] += 1
        out = {}
        record = []
        for q in req.get("questions", []):
            qid, default = q["id"], q.get("default")
            a = answers.get(qid) or {}
            choice, probs = a.get("choice", default), a.get("probabilities") or {}
            gated = False
            # Vetoing Forge's play ("pass") and overruling its mulligan call need the big margin: every mulligan
            # override in the v2.2 and v3.1 arms (18 of them) went the wrong way. So does sending an attacker Forge
            # keeps home: blind judges preferred Forge's answer in all 8 such overrules audited, and the v3.1
            # post-mortem found them behind several lost games (Muldrotha traded into untapped blockers).
            big = ((kind == "action" and qid == "action" and choice == "pass") or kind == "mulligan"
                   or (kind == "attack" and default == "hold" and choice != "hold"))
            gate = self.pass_gate if big else self.gate
            raw = choice
            if choice != default and probs.get(choice, 1.0) - probs.get(default, 0.0) < gate:
                choice, gated = default, True
            out[qid] = choice
            label = next((o["text"] for o in q["options"] if o["id"] == choice), choice)
            rec = {"q": qid, "default": default, "choice": choice, "gated": gated,
                   "label": label[:90], "p": round(probs.get(choice, 0), 3)}
            if choice != default or gated:
                rec["default_label"] = next((o["text"] for o in q["options"] if o["id"] == default), default)[:90]
                rec["p_default"] = round(probs.get(default, 0), 3)
            if gated:  # what Jev wanted, so sub-margin preferences can be audited later
                rec["raw_choice"] = raw
                rec["raw_label"] = next((o["text"] for o in q["options"] if o["id"] == raw), raw)[:90]
                rec["margin"] = round(probs.get(raw, 0) - probs.get(default, 0), 3)
            if kind in ("search", "mulligan") or len(q["options"]) <= 3:
                rec["n_options"] = len(q["options"])
            if kind == "action" and qid == "action":  # which options the memo's plan named, for adherence audits
                marked = [o["id"] for o in q["options"] if plan_marker(g["memo"], o["text"])]
                if marked:
                    rec["plan_marked"] = marked
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
        rec = {"type": "decision", "game": game, "turn": state.get("turn"), "phase": state.get("phase"),
               "kind": kind, "ms": ms, "escalated": escalated,
               "esc_p": None if esc is None else round(esc, 3), "answers": record}
        if getattr(self, "log_state", LOG_FULL_STATE):  # for offline audits of single decisions (~10x bigger logs)
            rec["state"] = state
            rec["memo"] = g["memo"]
            rec["questions"] = req.get("questions", [])
            rec["context"] = {k: req[k] for k in ("window", "stack_top") if k in req}
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
