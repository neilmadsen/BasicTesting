"""A Claude model as the pilot's executor, in place of Jev.

Jev answers each decision as a calibrated distribution over the options. This provider asks a Claude model
(Haiku 5.5 by default) the same questions on the same state and parses the same shape back:
{qid: {"choice": option_id, "probabilities": {option_id: p}}} for choice questions and {"noul": p} for the
escalation check. The model's probabilities are self-reported, not calibrated, and the executor's gates
(margins over Forge's default, the pass gate) were tuned on Jev's; read results with that in mind.

Calls go through `claude -p` (edhkit/claude_cli.py) like every other model call in the repo.
"""
from __future__ import annotations

import json
import re
import threading

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


class ClaudeExecutorProvider:
    name = "claude"

    def __init__(self, model: str = "claude-haiku-5-5", effort: str = "medium"):
        self.model, self.effort = model, effort
        self.usage = {"requests": 0, "failures": 0, "unparsed": 0, "input_chars": 0, "output_chars": 0}
        self._lock = threading.Lock()

    def evaluate(self, state, questions: dict[str, dict], progress: str = "") -> dict[str, dict]:
        prompt = _prompt(state, questions)
        try:
            text = run(SYSTEM, prompt, self.model, self.effort, timeout=240)
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
