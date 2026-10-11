"""A Claude model as the pilot's executor, in place of Jev.

Jev answers each decision as a calibrated distribution over the options. This provider asks a Claude model
(Haiku 5.5 by default) the same questions on the same state and parses the same shape back:
{qid: {"choice": option_id, "probabilities": {option_id: p}}} for choice questions and {"noul": p} for the
escalation check. The model's probabilities are self-reported, not calibrated, and the executor's gates
(margins over Forge's default, the pass gate) were tuned on Jev's; read results with that in mind.

Transport: with an ANTHROPIC_API_KEY (environment or .env) calls go straight to the Messages API through the
Anthropic SDK, with the deck plan and the memo cached as a prefix. The key is passed to the client, never
exported, so the strategist's and judge's `claude -p` calls keep drawing on the plan, not on API credits.
Without a key, calls go through `claude -p` like every other model call in the repo (about 10 s each).
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from .claude_cli import ClaudeCallFailed, run

SYSTEM = (
    "You are the tactical executor for our seat in a four-player Magic: The Gathering Commander game. You get "
    "our deck plan, the strategist's memo for this turn, the board as JSON (with oracle text), and one or more "
    "questions, each with option ids and option text (some options carry tags saying the memo's plan or HOLD "
    "names them). Answer every question from this exact position. Prefer the memo's plan unless the board "
    "has changed in a way that makes it wrong. Never invent option ids.\n\n"
    "Reply with only a JSON object, no prose and no code fence:\n"
    '{"<question id>": {"choice": "<option id>", "probabilities": {"<option id>": <p>, ...}}, ...}\n'
    "Give each choice question probabilities over all its options that sum to 1: your honest belief that each "
    "option is the best play. For a question of type noul, reply {\"noul\": <p>} with the probability that the "
    "statement in its \"true\" criterion holds."
)


def _prompt(state: dict, questions: dict) -> str:
    qs = {}
    for qid, q in questions.items():
        instr = q.get("instructions")
        qs[qid] = {"type": q.get("type", "choice"),
                   "question": instr.get("question") if isinstance(instr, dict) else instr,
                   "how_to_decide": instr.get("how_to_decide", "") if isinstance(instr, dict) else "",
                   "options": q.get("criteria", {})}
    return ("STATE:\n" + json.dumps(state, ensure_ascii=False) + "\n\nQUESTIONS:\n"
            + json.dumps(qs, ensure_ascii=False, indent=1) + "\n\nAnswer as JSON.")


def _parse(text: str, questions: dict) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    out = {}
    for qid, q in questions.items():
        a = raw.get(qid)
        if not isinstance(a, dict):
            continue
        if q.get("type") == "noul":
            try:
                out[qid] = {"noul": float(a.get("noul"))}
            except (TypeError, ValueError):
                pass
            continue
        opts = set(q.get("criteria", {}))
        probs = {k: float(v) for k, v in (a.get("probabilities") or {}).items()
                 if k in opts and isinstance(v, (int, float))}
        choice = a.get("choice") if a.get("choice") in opts else (max(probs, key=probs.get) if probs else None)
        if choice is None:
            continue
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()} if total > 0 else {choice: 1.0}
        out[qid] = {"choice": choice, "probabilities": probs}
    return out


KEY_VARS = ("EDH_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")  # the first is safe to set environment-wide


def api_key() -> str | None:
    """The executor's API key: EDH_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY from the environment, else from the
    repo's .env (read, not exported). Prefer EDH_ANTHROPIC_API_KEY in environment settings: an exported
    ANTHROPIC_API_KEY would also move the strategist's and judge's `claude -p` calls onto API billing."""
    for var in KEY_VARS:
        if os.environ.get(var):
            return os.environ[var]
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for var in KEY_VARS:
            for line in env.read_text().splitlines():
                m = re.match(rf"\s*(?:export\s+)?{var}\s*=\s*['\"]?([^'\"\s]+)", line)
                if m:
                    return m.group(1)
    return None


def _api_messages(state: dict, questions: dict) -> tuple[list, list]:
    """System and user content split for prefix caching: the deck plan (fixed for the game) and the memo
    (fixed for a turn) come first behind breakpoints; the board, decision and questions change every call."""
    rest = dict(state)
    plan = rest.pop("deck_plan", "")
    memo = rest.pop("strategy_memo", "")
    log = rest.pop("game_log", None) or {}
    system = [{"type": "text", "text": SYSTEM + "\n\nDECK PLAN:\n" + plan, "cache_control": {"type": "ephemeral"}}]
    user = []
    # completed rounds never change: one block each, a breakpoint on the last, so each round is written once
    done = log.get("completed_rounds") or []
    if done:
        user.append({"type": "text", "text": "GAME SO FAR (completed rounds, oldest first):"})
        user += [{"type": "text", "text": r} for r in done]
        user[-1]["cache_control"] = {"type": "ephemeral"}
    user.append({"type": "text", "text": "STRATEGY MEMO:\n" + memo, "cache_control": {"type": "ephemeral"}})
    if log.get("this_round"):
        rest["game_log_this_round"] = log["this_round"]
    user.append({"type": "text", "text": _prompt(rest, questions)})
    return system, user


class ClaudeExecutorProvider:
    name = "claude"

    def __init__(self, model: str = "claude-haiku-5-5", effort: str = "medium", transport: str = "auto"):
        self.model, self.effort = model, effort
        key = api_key() if transport in ("auto", "api") else None
        if transport == "api" and not key:
            raise SystemExit("ANTHROPIC_API_KEY not found in the environment or .env")
        self.client = None
        if key:
            import anthropic  # optional dependency; only the API transport needs it
            self.client = anthropic.Anthropic(api_key=key, max_retries=3)
        self.transport = "api" if self.client else "cli"
        self.usage = {"requests": 0, "failures": 0, "unparsed": 0, "input_chars": 0, "output_chars": 0,
                      "input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                      "output_tokens": 0}
        self._lock = threading.Lock()

    def _call_api(self, state, questions) -> str:
        import anthropic
        system, user = _api_messages(state, questions)
        try:
            r = self.client.messages.create(model=self.model, max_tokens=8000, system=system,
                                            output_config={"effort": self.effort},
                                            messages=[{"role": "user", "content": user}])
        except anthropic.APIError as e:
            raise ClaudeCallFailed(str(e)[:200]) from e
        with self._lock:
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"):
                self.usage[k] += getattr(r.usage, k, 0) or 0
        if r.stop_reason == "refusal":
            raise ClaudeCallFailed("refusal")
        return "".join(b.text for b in r.content if b.type == "text")

    def evaluate(self, state, questions: dict[str, dict], progress: str = "") -> dict[str, dict]:
        prompt = _prompt(state, questions)
        try:
            text = (self._call_api(state, questions) if self.client
                    else run(SYSTEM, prompt, self.model, self.effort, timeout=240))
        except ClaudeCallFailed:
            with self._lock:
                self.usage["requests"] += 1
                self.usage["failures"] += 1
            return {}  # the executor falls back to Forge's default, as with any missing answer
        out = _parse(text, questions)
        with self._lock:
            self.usage["requests"] += 1
            self.usage["input_chars"] += len(SYSTEM) + len(prompt)
            self.usage["output_chars"] += len(text)
            if len(out) < len(questions):
                self.usage["unparsed"] += 1
        return out

    def cost_usd(self, price_in: float = 0.10, price_out: float = 0.50) -> float:
        """Haiku 5.5 list prices per million tokens (prompts under 100K); cache reads 0.1x, 5-minute writes 1.25x."""
        u = self.usage
        return round((u["input_tokens"] * price_in + u["cache_read_input_tokens"] * price_in * 0.1
                      + u["cache_creation_input_tokens"] * price_in * 1.25 + u["output_tokens"] * price_out) / 1e6, 4)
