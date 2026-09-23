"""Two-layer pilot for Forge games: an LLM strategist and a Jev executor.

The Java side (pilot/src/edh/pilot) hands our main-phase priority decisions to
this sidecar over localhost HTTP: board state plus the plays Forge's evaluator
approves (each already has legal targets and a payable cost) plus "pass".

  strategist (slow, occasional): once per turn of ours, an LLM reads the deck
      plan and the board and writes a short strategy memo. It runs in a
      background thread; decisions never wait for it.
  executor (fast, every decision): Jev answers one Choice question: which
      option now, given the deck plan, the latest memo and the board.
      Low-confidence answers defer to Forge's own pick.

Strategist providers:
  static     — no LLM; the memo is empty and Jev works from the deck plan alone
  claude-cli — headless Claude Code (`claude -p`), uses the session's own login
  anthropic  — Anthropic Python SDK (needs `pip install anthropic` and credentials)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

from . import jev

STRATEGIST_MODEL = os.environ.get("EDH_STRATEGIST_MODEL", "claude-opus-5")
# Overrule Forge's own pick only when Jev's top choice beats it by this probability margin.
CONFIDENCE_GATE = float(os.environ.get("EDH_PILOT_GATE", "0.15"))
PLAN_CHARS = 5000

EXECUTOR_QUESTION = (
    "We are `board.me` in a four-player Commander game. It is our main phase, the stack is empty, and we "
    "have priority. Pick the single best action to take right now. Follow `deck_plan` and the latest "
    "`strategy_memo`. Options in zone Graveyard are cast or played from our graveyard, which spends that "
    "permanent type's recursion for the turn and keeps the cards in hand. Choose `pass` only when holding "
    "our mana and cards is better than every listed action."
)
STRATEGIST_SYSTEM = (
    "You are the strategist for a Magic: The Gathering Commander deck in a four-player game. A fast "
    "executor model picks each individual play; it reads your memo before every decision. Write for it: "
    "concrete, card-named, ordered priorities. Plain text, at most 120 words, three labelled lines: "
    "PRIORITIES, THREAT, HOLD."
)


def _section(md: str, pattern: str, limit: int) -> str:
    """Pull one markdown section (heading matching pattern) out of notes.md."""
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


def _option_text(o: dict) -> str:
    tg = f" → targets: {', '.join(o['targets'])}" if o.get("targets") else ""
    zone = o.get("zone", "?").title()
    note = ""
    if o.get("source", "").startswith("forge-declined"):
        note = f" (Forge's heuristic AI would not make this play: {o['source'].split(':', 1)[1]})"
    return f"{o['kind']} {o['card']} (from {zone}): {o['text']}{tg}{note}"


class Pilot:
    def __init__(self, plan: str, strategist: str = "static", log_dir: Path | None = None,
                 model: str = STRATEGIST_MODEL, gate: float = CONFIDENCE_GATE, sync: bool = True):
        self.plan = plan
        self.strategist = strategist
        self.sync = sync
        self.model = model
        self.gate = gate
        self.provider = jev.get_provider()
        if isinstance(self.provider, jev.LexicalProvider):
            raise SystemExit("the Jev pilot needs TYPESAFE_API_KEY (in env or .env)")
        self.log_dir = log_dir
        self._log_lock = threading.Lock()
        self._memos: dict[str, dict] = {}       # game -> {"memo", "turn", "pending"}
        self._memo_lock = threading.Lock()
        self.stats = {"decisions": 0, "fallbacks": 0, "errors": 0, "differs_from_forge": 0,
                      "latency_ms": [], "strategist_calls": 0, "strategist_ms": [], "strategist_errors": 0}
        self._server: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------------ server
    def start(self) -> str:
        pilot = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence default access log
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/decide":
                    out = pilot.decide(body)
                else:
                    out = {"ok": True}
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
    def _memo(self, game: str, state: dict) -> str:
        """Latest memo for this game, refreshing once per turn of ours.

        sync (default): the first decision of each of our turns waits for the new memo,
        like a player thinking before acting. A simulation can pause, so the executor
        always works from a current plan. async: never wait; use the last finished
        memo (for real-time settings where the game can't pause).
        """
        if self.strategist == "static":
            return ""
        turn = state.get("turn", 0)
        with self._memo_lock:
            entry = self._memos.setdefault(game, {"memo": "", "turn": -1, "pending": False})
            start = entry["turn"] != turn and not entry["pending"]
            if start:
                entry["pending"] = True
                entry["turn"] = turn
            previous = entry["memo"]
        if start:
            if self.sync:
                self._refresh(game, state, previous)
            else:
                threading.Thread(target=self._refresh, args=(game, state, previous), daemon=True).start()
        with self._memo_lock:
            return self._memos[game]["memo"]

    def _refresh(self, game: str, state: dict, previous: str) -> None:
        prompt = (f"Deck plan:\n{self.plan}\n\nCurrent board (JSON):\n{json.dumps(state, ensure_ascii=False)}\n\n"
                  f"Previous memo:\n{previous or '(none)'}\n\nWrite the new memo.")
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
        except Exception as e:  # never let the strategist break a game
            self.stats["strategist_errors"] += 1
            memo = ""
            print(f"[pilot] strategist error: {e}")
        self.stats["strategist_calls"] += 1
        self.stats["strategist_ms"].append(int((time.time() - t0) * 1000))
        with self._memo_lock:
            entry = self._memos[game]
            if memo:
                entry["memo"] = memo[:1500]
            entry["pending"] = False
        self._log({"type": "memo", "game": game, "turn": state.get("turn"), "memo": memo,
                   "ms": self.stats["strategist_ms"][-1]})

    def _anthropic(self, prompt: str) -> str:
        import anthropic  # optional dependency; only this provider needs it
        client = anthropic.Anthropic()
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
    def decide(self, req: dict) -> dict:
        game = req.get("game", "?")
        options = req.get("options", [])
        default = req.get("forge_default", "pass")
        state = req.get("state", {})
        memo = self._memo(game, state)
        criteria = {o["id"]: _option_text(o) for o in options}
        criteria["pass"] = "Take no further action this phase: hold remaining mana and cards"
        question = {"action": {"type": "choice",
                               "instructions": {"question": EXECUTOR_QUESTION},
                               "criteria": criteria}}
        jstate = {"deck_plan": self.plan, "strategy_memo": memo or "(none yet)", "board": state}
        t0 = time.time()
        choice, conf, probs, fallback = default, None, None, False
        try:
            ans = self.provider.evaluate(jstate, question)["action"]
            choice, conf, probs = ans["choice"], ans.get("confidence"), ans.get("probabilities")
            # Margin gate: overrule Forge only when Jev clearly prefers something else.
            p_top = (probs or {}).get(choice, 1.0)
            p_def = (probs or {}).get(default, 0.0)
            if choice != default and p_top - p_def < self.gate:
                choice, fallback = default, True
        except Exception as e:
            self.stats["errors"] += 1
            fallback = True
            print(f"[pilot] jev error, using Forge's pick: {e}")
        ms = int((time.time() - t0) * 1000)
        self.stats["decisions"] += 1
        self.stats["latency_ms"].append(ms)
        self.stats["fallbacks"] += fallback
        self.stats["differs_from_forge"] += choice != default
        chosen = next((o for o in options if o["id"] == choice), None)
        self._log({"type": "decision", "game": game, "turn": state.get("turn"), "phase": state.get("phase"),
                   "n_options": len(options), "forge_default": default, "choice": choice,
                   "chosen": f"{chosen['kind']} {chosen['card']} ({chosen['zone']})" if chosen else "pass",
                   "confidence": conf, "fallback": fallback, "ms": ms,
                   "top": sorted((probs or {}).items(), key=lambda kv: -kv[1])[:3]})
        return {"choice": choice}

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
        return {
            "strategist": self.strategist, "strategist_model": self.model if self.strategist != "static" else None,
            "decisions": s["decisions"], "errors": s["errors"],
            "fallback_rate": round(s["fallbacks"] / s["decisions"], 3) if s["decisions"] else 0,
            "differs_from_forge_rate": round(s["differs_from_forge"] / s["decisions"], 3) if s["decisions"] else 0,
            "latency_ms_avg": int(mean(lat)) if lat else None,
            "latency_ms_p95": lat[int(len(lat) * 0.95)] if lat else None,
            "jev_input_tokens": tokens, "jev_usd": round(tokens / 1e6 * jev.PRICE_PER_MTOK, 4),
            "strategist_calls": s["strategist_calls"], "strategist_errors": s["strategist_errors"],
            "strategist_ms_avg": int(mean(s["strategist_ms"])) if s["strategist_ms"] else None,
        }
