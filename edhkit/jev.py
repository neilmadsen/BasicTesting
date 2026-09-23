"""Semantic card screening with TypeSafe's Jev (System One decision model).

Why Jev: it returns calibrated, typed answers (Score / Noul / Choice) for about
$0.04 per million input tokens, fast enough to judge *every* legal card in a
color identity against a strategy brief. That turns hidden-gem hunting from
"hope someone mentioned it on Reddit" into an exhaustive screen. The agent's
own judgement then works on a few hundred candidates instead of thirty thousand.

Request shape follows https://docs.typesafe.ai/api: one request carries the
strategy brief as `state` and up to ~100 per-card questions (speculative
fan-out). Each question embeds its card as structured data so there's no
indirection for the model to follow. Answers are cached on disk by content hash.

Without TYPESAFE_API_KEY, `LexicalProvider` gives a crude keyword-overlap
ranking so the pipeline still runs; the skills tell the agent to lean on its
own reading and Scryfall queries in that case.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import net
from .cards import Card
from .paths import DATA, ROOT

API_BASE = os.environ.get("TYPESAFE_API_BASE", "https://api.typesafe.ai")
MODEL = os.environ.get("EDH_JEV_MODEL", "jev-latest")
PRICE_PER_MTOK = 0.042
# Per-request budget: docs allow 64k total and 32k for state + longest question.
MAX_REQUEST_TOKENS = 44_000
MAX_QUESTIONS_PER_REQUEST = 120
MAX_STATE_TOKENS = 12_000
WORKERS = int(os.environ.get("EDH_JEV_WORKERS", "4"))

# Versioned so changing the rubric invalidates the cache instead of mixing scales.
RUBRIC_VERSION = "fit-v1"
FIT_LEVELS = [
    "Off-plan: does nothing for this strategy, or works against it",
    "Generic: playable in these colors but has no specific connection to this strategy",
    "Supportive: fills a role the deck needs (ramp, card draw, interaction, protection) or ties loosely to the theme",
    "Synergistic: directly advances the strategy; interacts with the commander or the deck's key mechanic",
    "Core: an engine, payoff, or enabler this exact strategy would be built around",
]
FIT_QUESTION = (
    "How much would adding `card` to the Commander deck described in the state improve that deck's ability "
    "to execute its strategy? Judge the card's synergy with the commander and the stated plan. Raw power "
    "matters only insofar as it serves the plan. Cards the state lists under avoid are Off-plan."
)


def load_api_key() -> str | None:
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key.strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?TYPESAFE_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
            if m:
                return m.group(1)
    return None


def est_tokens(obj) -> int:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return math.ceil(len(s) / 3.6)


def card_payload(c: Card) -> dict:
    d = {"name": c.name, "mana_cost": c.mana_cost or "", "type": c.type_line, "text": c.text}
    if c.pt:
        d["stats"] = c.pt
    return d


# --------------------------------------------------------------------------- cache

class _Cache:
    def __init__(self, path: Path = DATA / "jev_cache.db"):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.execute("CREATE TABLE IF NOT EXISTS answers (k TEXT PRIMARY KEY, v TEXT)")
        self.lock = threading.Lock()

    @staticmethod
    def key(state, question) -> str:
        blob = json.dumps([MODEL, state, question], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def get(self, k: str):
        with self.lock:
            r = self.con.execute("SELECT v FROM answers WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else None

    def put_many(self, items: list[tuple[str, dict]]) -> None:
        with self.lock:
            self.con.executemany("INSERT OR REPLACE INTO answers VALUES (?,?)", [(k, json.dumps(v)) for k, v in items])
            self.con.commit()


# --------------------------------------------------------------------------- providers

@dataclass
class Judgement:
    card: Card
    value: float            # score (0..4) for rank, probability (0..1) for grep
    confidence: float | None = None
    probabilities: dict | None = None


class JevProvider:
    name = "jev"

    def __init__(self, api_key: str, dry_run: bool = False):
        self.api_key = api_key
        self.dry_run = dry_run
        self.cache = _Cache()
        self.usage = {"input_tokens": 0, "requests": 0, "cached": 0}
        self._ulock = threading.Lock()

    def _post(self, state, questions: dict) -> dict:
        body = {"model": MODEL, "state": state, "questions": questions}
        if self.dry_run:
            raise _DryRun(body)
        resp = net.post_json(
            f"{API_BASE}/v1/systemone", body,
            headers={"Authorization": f"Bearer {self.api_key}"}, timeout=120, retries=5,
        )
        with self._ulock:
            self.usage["input_tokens"] += resp.get("usage", {}).get("input_tokens", 0)
            self.usage["requests"] += 1
        return resp["answers"]

    def evaluate(self, state, questions: dict[str, dict], progress: str = "") -> dict[str, dict]:
        """Evaluate many questions against one state, batching + caching transparently."""
        answers: dict[str, dict] = {}
        pending: list[tuple[str, dict, str]] = []
        for qid, q in questions.items():
            k = self.cache.key(state, q)
            hit = self.cache.get(k)
            if hit is not None:
                answers[qid] = hit
                self.usage["cached"] += 1
            else:
                pending.append((qid, q, k))
        state_tok = est_tokens(state)
        if state_tok > MAX_STATE_TOKENS:
            raise ValueError(f"state is ~{state_tok} tokens; keep briefs under {MAX_STATE_TOKENS} (Jev reads best with focused state)")
        batches: list[list[tuple[str, dict, str]]] = []
        cur, cur_tok = [], state_tok
        for item in pending:
            t = est_tokens(item[1]) + 8
            if cur and (cur_tok + t > MAX_REQUEST_TOKENS or len(cur) >= MAX_QUESTIONS_PER_REQUEST):
                batches.append(cur)
                cur, cur_tok = [], state_tok
            cur.append(item)
            cur_tok += t
        if cur:
            batches.append(cur)

        def run(batch):
            qs = {qid: q for qid, q, _ in batch}
            res = self._post(state, qs)
            self.cache.put_many([(k, res[qid]) for qid, _, k in batch if qid in res])
            return {qid: res[qid] for qid, _, _ in batch if qid in res}

        if batches and self.dry_run:
            run(batches[0])  # raises _DryRun with the first payload
        done = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(run, b) for b in batches]
            for fut in as_completed(futs):
                answers.update(fut.result())
                done += 1
                if progress and sys.stderr.isatty():
                    print(f"\r  {progress}: {done}/{len(batches)} requests", end="", file=sys.stderr)
        if progress and batches and sys.stderr.isatty():
            print(file=sys.stderr)
        return answers

    def cost_estimate(self, state, questions: dict) -> tuple[int, float]:
        tok = sum(est_tokens(q) for q in questions.values())
        n_req = max(1, math.ceil(tok / (MAX_REQUEST_TOKENS - est_tokens(state))))
        total = tok + n_req * est_tokens(state)
        return total, total / 1e6 * PRICE_PER_MTOK


class _DryRun(Exception):
    def __init__(self, body):
        super().__init__("dry run")
        self.body = body


class LexicalProvider:
    """Keyword-overlap stand-in used when no API key is configured. Crude on purpose."""

    name = "lexical"
    STOP = set("""a an the and or of to in on for with your you it its this that is are be as at by from
        into onto each any all when whenever if then than may can one two three card cards deck commander
        strategy creature creatures spell spells player players opponent opponents turn game control target
        until end put get gets has have more less up down out other another use using want wants play
        plays like also not no only them they their there where which who whose while about over under""".split())

    def __init__(self):
        self.usage = {"input_tokens": 0, "requests": 0, "cached": 0}

    def _terms(self, text: str) -> dict[str, float]:
        words = re.findall(r"[a-z][a-z\-+/']{2,}", text.lower())
        tf: dict[str, float] = {}
        for w in words:
            if w not in self.STOP:
                tf[w] = tf.get(w, 0) + 1
        return tf

    def score(self, query_text: str, cards: list[Card]) -> dict[str, float]:
        q = self._terms(query_text)
        # rough idf from the candidate pool itself
        df: dict[str, int] = {}
        docs = {}
        for c in cards:
            terms = set(self._terms(c.text + " " + c.type_line))
            docs[c.oracle_id] = terms
            for t in terms:
                df[t] = df.get(t, 0) + 1
        n = max(len(cards), 1)
        out = {}
        for c in cards:
            s = sum(min(qf, 3) * math.log(1 + n / (1 + df.get(t, 0))) for t, qf in q.items() if t in docs[c.oracle_id])
            out[c.oracle_id] = s
        return out


def get_provider(dry_run: bool = False):
    key = load_api_key()
    if key or dry_run:
        return JevProvider(key or "DRY-RUN", dry_run=dry_run)
    return LexicalProvider()


# --------------------------------------------------------------------------- high-level ops

def _brief_state(brief: str) -> dict:
    return {"deck_brief": brief.strip()}


def rank(cards: list[Card], brief: str, provider=None, dry_run: bool = False) -> tuple[list[Judgement], dict]:
    """Score every card 0-4 for fit with the strategy brief. Returns (sorted judgements, usage)."""
    provider = provider or get_provider(dry_run)
    if isinstance(provider, LexicalProvider):
        raw = provider.score(brief, cards)
        mx = max(raw.values(), default=0) or 1
        js = [Judgement(c, 4 * raw[c.oracle_id] / mx) for c in cards]
        js.sort(key=lambda j: j.value, reverse=True)
        return js, {"provider": "lexical", **provider.usage}
    state = _brief_state(brief)
    questions = {}
    for i, c in enumerate(cards):
        questions[f"c{i}"] = {
            "type": "score",
            "instructions": {"card": card_payload(c), "question": FIT_QUESTION},
            "criteria": FIT_LEVELS,
        }
    try:
        ans = provider.evaluate(state, questions, progress="jev rank")
    except _DryRun as d:
        tok, usd = provider.cost_estimate(state, questions)
        return [], {"provider": "jev", "dry_run": True, "first_request": d.body,
                    "questions": len(questions), "est_tokens": tok, "est_usd": round(usd, 4)}
    js = []
    for i, c in enumerate(cards):
        a = ans.get(f"c{i}")
        if a:
            js.append(Judgement(c, float(a.get("score", 0)), a.get("confidence"), a.get("probabilities")))
    js.sort(key=lambda j: j.value, reverse=True)
    return js, {"provider": "jev", **provider.usage}


def grep(cards: list[Card], requirement: str, context: str = "", provider=None,
         dry_run: bool = False) -> tuple[list[Judgement], dict]:
    """Semantic grep: P(card satisfies requirement) for every card."""
    provider = provider or get_provider(dry_run)
    if isinstance(provider, LexicalProvider):
        raw = provider.score(requirement, cards)
        mx = max(raw.values(), default=0) or 1
        js = [Judgement(c, raw[c.oracle_id] / mx) for c in cards]
        js.sort(key=lambda j: j.value, reverse=True)
        return js, {"provider": "lexical", **provider.usage}
    state = {"deck_context": context.strip()} if context.strip() else {"task": "Screen Magic: The Gathering cards against a requirement."}
    questions = {}
    for i, c in enumerate(cards):
        questions[f"c{i}"] = {
            "type": "noul",
            "instructions": {"card": card_payload(c), "requirement": requirement,
                             "question": "Does `card` satisfy `requirement`? Read the card's rules text literally."},
            "criteria": {"true": "The card's own text clearly does what the requirement describes",
                         "false": "The card does not do this, or only in a stretched, incidental way"},
        }
    try:
        ans = provider.evaluate(state, questions, progress="jev grep")
    except _DryRun as d:
        tok, usd = provider.cost_estimate(state, questions)
        return [], {"provider": "jev", "dry_run": True, "first_request": d.body,
                    "questions": len(questions), "est_tokens": tok, "est_usd": round(usd, 4)}
    js = [Judgement(c, float(ans[f"c{i}"]["noul"])) for i, c in enumerate(cards) if f"c{i}" in ans]
    js.sort(key=lambda j: j.value, reverse=True)
    return js, {"provider": "jev", **provider.usage}


def ask(state, questions: dict, dry_run: bool = False) -> dict:
    """Raw access for one-off structured judgements (e.g. comparing archetypes)."""
    p = get_provider(dry_run)
    if isinstance(p, LexicalProvider):
        raise SystemExit("jev ask needs TYPESAFE_API_KEY (in env or .env)")
    try:
        return p.evaluate(state, questions)
    except _DryRun as d:
        return {"dry_run": True, "request": d.body}
