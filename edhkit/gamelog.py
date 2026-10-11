"""A running digest of the game so far, built from the states the pilot sees.

The executor sees a snapshot: the board, the last dozen or so casts (`recent_casts`, a rolling window), each
player's life flow and the memo. A human player also remembers the story: who has been attacking whom, which
opponent held up a counterspell, where the removal went, what died. This keeps that story as one line per
round, events in order with their player:

    Round 5: us cast Demonic Tutor; us cast Deadly Rollick targeting Atarka, World Render; P2 cast Y'shtola.
        Triggers: us Ring of Evos Isle x6. Life: P3 37->32, us 37->33. Left the battlefield: P3 Atarka, World Render

Completed rounds never change, so a model executor can cache them as a prefix (see edhkit/llm_executor.py).
Built only from what the pilot already receives, so it works the same live and when rebuilt from a logged run.
"""
from __future__ import annotations

import re
from collections import Counter

MAX_EVENTS_PER_TURN = 14
EVENT_CHARS = 110


def _names(entries: list[str]) -> Counter:
    """Nonland, nontoken permanent names on a battlefield list ("Name 3/3 {..} [..] x2")."""
    out = Counter()
    for e in entries:
        if "[land]" in e or "[token]" in e:
            continue
        name = re.split(r" -?\d+/-?\d+| \[| \{| x\d+| \(tapped", e)[0].strip()
        n = int(m.group(1)) if (m := re.search(r" x(\d+)\b", e)) else 1
        out[name] += n
    return out


def _short(event: str) -> str:
    event = re.sub(r" \(\d+\)", "", event)           # Forge card ids
    event = event.replace("targeting [", "targeting ").replace("]", "")
    return event[:EVENT_CHARS]


class GameLog:
    def __init__(self):
        self.turns: dict[int, dict] = {}   # turn -> {"active", "events", "life_start", "life_end", "left", "lost"}
        self.window: list[str] = []        # last recent_casts seen
        self.prev: dict | None = None      # last state seen
        self.seats = 0

    # ------------------------------------------------------------------ feeding
    def update(self, state: dict) -> None:
        turn = state.get("turn")
        if not isinstance(turn, int) or turn < 1:
            return
        players = state.get("players", [])
        self.seats = self.seats or len(players)
        t = self.turns.setdefault(turn, {"active": self._label(state, state.get("active")), "events": [],
                                         "life_start": self._lives(self.prev) if self.prev else self._lives(state),
                                         "life_end": {}, "left": [], "lost": []})
        # new events: the part of the rolling window after its overlap with the last window
        cur = list(state.get("recent_casts") or [])
        k = next((k for k in range(min(len(self.window), len(cur)), 0, -1) if self.window[-k:] == cur[:k]), 0)
        if cur:
            t["events"].extend(_short(e) for e in cur[k:])
            self.window = cur
        # what left the battlefield since the last state (died, exiled, bounced), and who is out
        if self.prev:
            before = {p["name"]: _names(p.get("battlefield", [])) for p in self.prev.get("players", [])}
            for p in players:
                gone = before.get(p["name"], Counter()) - _names(p.get("battlefield", []))
                who = "us" if p.get("is_me") else p["name"]
                t["left"].extend(f"{who} {n}" + (f" x{c}" if c > 1 else "") for n, c in gone.items())
                was = next((q for q in self.prev.get("players", []) if q["name"] == p["name"]), {})
                if p.get("lost") and not was.get("lost"):
                    t["lost"].append(who)
        t["life_end"] = self._lives(state)
        self.prev = state

    @staticmethod
    def _label(state: dict, name: str | None) -> str:
        return "us" if name and name == state.get("me") else (name or "?")

    @staticmethod
    def _lives(state: dict | None) -> dict:
        if not state:
            return {}
        return {("us" if p.get("is_me") else p["name"]): p.get("life") for p in state.get("players", [])}

    # ------------------------------------------------------------------ reading
    def _round(self, r: int, turns: list[int]) -> str:
        """One round in order. Events carry their player; the turn an event lands in is only when the pilot
        next saw a state, so the digest is per round, not per turn."""
        casts, trig, left, lost = [], Counter(), [], []
        for turn in turns:
            t = self.turns[turn]
            for e in t["events"]:
                m = re.match(r"^(\S+) triggered (.+)$", e)
                if m:
                    trig[f"{m.group(1)} {m.group(2)}"] += 1
                else:
                    casts.append(e)
            left += t["left"]
            lost += t["lost"]
        first, last = self.turns[turns[0]], self.turns[turns[-1]]
        parts = casts[:MAX_EVENTS_PER_TURN * 2] + ([f"(+{len(casts) - 2 * MAX_EVENTS_PER_TURN} more)"]
                                                   if len(casts) > 2 * MAX_EVENTS_PER_TURN else [])
        text = f"Round {r}: " + ("; ".join(parts) if parts else "no casts seen")
        if trig:
            text += ". Triggers: " + ", ".join(f"{k} x{v}" for k, v in trig.most_common(6))
        life = [f"{p} {a}->{last['life_end'][p]}" for p, a in first["life_start"].items()
                if p in last["life_end"] and a is not None and last["life_end"][p] != a]
        if life:
            text += ". Life: " + ", ".join(life)
        if left:
            text += ". Left the battlefield: " + ", ".join(left[:12])
        if lost:
            text += ". Out of the game: " + ", ".join(lost)
        return text

    def rounds(self, current_turn: int | None = None) -> tuple[list[str], str]:
        """(completed rounds as text blocks, the current round so far). A round is one turn per seat."""
        seats = max(self.seats, 1)
        by_round: dict[int, list[int]] = {}
        for turn in sorted(self.turns):
            by_round.setdefault((turn - 1) // seats + 1, []).append(turn)
        cur_round = ((current_turn or max(self.turns, default=1)) - 1) // seats + 1
        done = [self._round(r, ts) for r, ts in sorted(by_round.items()) if r < cur_round]
        now = self._round(cur_round, by_round[cur_round]).replace(f"Round {cur_round}:", f"Round {cur_round} so far:", 1) \
            if cur_round in by_round else ""
        return done, now
