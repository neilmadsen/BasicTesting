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

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

from . import jev

STRATEGIST_MODEL = os.environ.get("EDH_STRATEGIST_MODEL", "claude-opus-5-5")
# Overrule Forge's own answer only when Jev's choice beats it by this probability margin.
CONFIDENCE_GATE = float(os.environ.get("EDH_PILOT_GATE", "0.15"))
ESCALATE_THRESHOLD = float(os.environ.get("EDH_PILOT_ESCALATE", "0.6"))
MAX_ESCALATIONS_PER_GAME = int(os.environ.get("EDH_PILOT_MAX_ESCALATIONS", "8"))
PLAN_CHARS = 5000

STRATEGIST_SYSTEM = (
    "You are the strategist for a Magic: The Gathering Commander deck in a four-player game. A fast "
    "executor model makes each individual decision (casts, attacks, blocks, targets, sacrifices) and "
    "reads your memo before every one. Write for it: concrete, card-named, ordered. Plain text, at most "
    "150 words, four labelled lines: PRIORITIES, THREAT, HOLD, REPLAN IF (specific board events that "
    "would make this plan wrong)."
)

KIND_GUIDANCE = {
    "action": "Choose the single best action right now (see `window`). Follow the plan and memo; "
              "`pass` only when holding mana and cards beats every listed action.",
    "attack": "We are declaring attackers. For this creature, decide whether and whom to attack. Weigh the "
              "defending player's untapped blockers, whether we need it back as a blocker, the memo's THREAT, "
              "and any chance to finish a player.",
    "block": "An opponent is attacking. Pick a blocker for this attacker or none. Protect engine pieces named "
             "in the plan/memo unless the damage is dangerous; prefer blocks that kill the attacker and survive; "
             "chump only when the damage matters.",
    "mulligan": "Opening hand decision. Keep hands that can make their land drops and do something by turn 3 "
                "toward the plan; mulligan hands with 0-1 or 6+ lands.",
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
                      "threats (the memo's THREAT first) and beneficial ones at our own key permanents.",
    "optional-trigger": "One of our 'you may' triggers is resolving. Say yes when it helps our plan now; no when "
                        "it would hurt us (e.g. a cost we can't afford, a symmetric effect that helps opponents more).",
    "search": "We are searching a zone and take one card (a tutor, fetch land, ramp spell or recursion). Take "
              "the card that most advances the memo's PRIORITIES from this board: the missing engine piece, the "
              "answer to the current THREAT, or the land that fixes what our hand needs. Read each land's type "
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


def changes_since(memo_state: dict | None, state: dict) -> list[str]:
    """Notable, code-computed differences between two board snapshots."""
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
        dn = a["nonland"] - b["nonland"]
        if dn <= -3 or (dn <= -2 and b["nonland"] <= 5) or dn >= 4:
            notes.append(f"{who}: nonland permanents {b['nonland']}→{a['nonland']} ({dn:+d})")
        dc = a["creatures"] - b["creatures"]
        if dc <= -3 or dc >= 4:
            notes.append(f"{who}: creatures {b['creatures']}→{a['creatures']} ({dc:+d})")
        if a["me"]:
            gone = b["named"] - a["named"]
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
                 escalate: bool = True):
        self.plan = plan
        self.strategist = strategist
        self.model = model
        self.gate = gate
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
                                                 "escalations": 0, "esc_turn": -1})

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
        board = json.dumps({k: v for k, v in state.items() if k != "card_text"}, ensure_ascii=False)
        prompt = (f"Deck plan:\n{self.plan}\n\nCurrent board (JSON):\n{board}\n\n"
                  f"Previous memo:\n{g['memo'] or '(none)'}\n\nReason for this memo: {reason}\n\nWrite the new memo.")
        t0 = time.time()
        memo = ""
        try:
            if self.strategist == "claude-cli":
                # Lightweight headless call: neutral cwd (no project CLAUDE.md/skills), no tools,
                # our own system prompt, low effort. ~10 s instead of ~2 min for the full harness.
                out = subprocess.run(
                    ["claude", "-p", "--tools", "", "--no-session-persistence", "--effort", "low",
                     "--model", self.model, "--system-prompt", STRATEGIST_SYSTEM],
                    input=prompt, capture_output=True, text=True, timeout=180, cwd=tempfile.gettempdir())
                memo = out.stdout.strip()
            elif self.strategist == "anthropic":
                memo = self._anthropic(prompt)
        except Exception as e:
            self.stats["strategist_errors"] += 1
            print(f"[pilot] strategist error: {e}")
        ms = int((time.time() - t0) * 1000)
        self.stats["strategist_calls"] += 1
        self.stats["strategist_ms"].append(ms)
        with self._glock:
            if memo:
                g["memo"], g["memo_state"] = memo[:2000], state
            g["pending"] = False
        self._log({"type": "memo", "game": game, "turn": state.get("turn"), "reason": reason, "memo": memo, "ms": ms})

    def _anthropic(self, prompt: str) -> str:
        import anthropic  # optional dependency; only this provider needs it
        client = anthropic.Anthropic()
        # Opus 5.5: thinking is always on and effort defaults to medium, so set effort explicitly.
        resp = client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            system=STRATEGIST_SYSTEM,
            output_config={"effort": "low"},
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
            questions[q["id"]] = {"type": "choice",
                                  "instructions": {"question": q["prompt"], "how_to_decide": KIND_GUIDANCE.get(kind, "")},
                                  "criteria": {o["id"]: o["text"] for o in q["options"]}}
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
        changes = changes_since(g["memo_state"], state) if self.escalate else []
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
            if choice != default and probs.get(choice, 1.0) - probs.get(default, 0.0) < self.gate:
                choice, gated = default, True
            out[qid] = choice
            label = next((o["text"] for o in q["options"] if o["id"] == choice), choice)
            rec = {"q": qid, "default": default, "choice": choice, "gated": gated,
                   "label": label[:90], "p": round(probs.get(choice, 0), 3)}
            if choice != default or gated:
                rec["default_label"] = next((o["text"] for o in q["options"] if o["id"] == default), default)[:90]
                rec["p_default"] = round(probs.get(default, 0), 3)
            if kind in ("search", "mulligan") or len(q["options"]) <= 3:
                rec["n_options"] = len(q["options"])
            record.append(rec)
        # Speculative target questions only matter for the action actually taken.
        taken = "tgt_" + out.get("action", "") if kind == "action" else None
        for r in record:
            if taken is not None and r["q"].startswith("tgt_") and r["q"] != taken:
                r["unused"] = True
                continue
            ks["questions"] += 1
            ks["overrules"] += r["choice"] != r["default"]
            ks["gated"] += r["gated"]
        self._log({"type": "decision", "game": game, "turn": state.get("turn"), "phase": state.get("phase"),
                   "kind": kind, "ms": ms, "escalated": escalated,
                   "esc_p": None if esc is None else round(esc, 3), "answers": record})
        return {"answers": out}

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
