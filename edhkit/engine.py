"""Engine goldfish: how often does the deck assemble the thing its brief says it is built around?

The mana goldfish answers "can I cast my commander on time". This answers the deck's own thesis, from
an `engine` block in brief.md (several blocks for several packages):

    ```engine
    name: Upkeep engine
    by: 6
    commander
    2 of: regex:at the beginning of your upkeep
    1 of: Court of Ire; Court of Vantress; regex:you become the monarch
    held 1 of: tag:counterspell
    tutors: Mystical Tutor; Demonic Tutor
    ```

- `commander`: the commander must be cast.
- `N of: ...`: N different cards matching any of the `;`-separated terms must be *cast* (a card name,
  `regex:<pattern over rules text>`, `tag:<tagger role>`, or `type:<type-line word>`).
- `held N of: ...`: N matching cards in hand count (counterspells held up, combo pieces kept).
- `tutors:`: cards that, when cast, fetch the missing piece the engine needs most to hand.
- `by:`: the turn the plan needs it online by (reported, not enforced).

Simulation: the mana goldfish's land, ramp and colour model; each turn cast the commander if required,
then ramp, then a tutor if a piece is missing, then the cheapest affordable missing pieces. Online on turn
T when every requirement is met. It is a lower bound in some ways (no card draw beyond one a turn, no
cost reducers) and an upper bound in others (no opponents, no removal), and it is exact on the question it
asks: do the pieces show up, and can the mana deploy them, by the turn the plan needs.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from statistics import mean

from .analyze import Source, _can_pay, _enters_tapped, land_source, pips, ramp_effect, WUBRG
from .cards import Card
from .deck import Deck


@dataclass
class Req:
    n: int
    terms: list[str]
    held: bool = False
    label: str = ""
    members: set[str] = field(default_factory=set)   # deck card names that satisfy it


@dataclass
class Engine:
    name: str
    by: int | None = None
    commander: bool = False
    reqs: list[Req] = field(default_factory=list)
    tutors: list[str] = field(default_factory=list)


BLOCK = re.compile(r"```engine\s*\n(.*?)```", re.S)
REQ = re.compile(r"^(held\s+)?(\d+)\s+of\s*:\s*(.+)$", re.I)


def parse(text: str) -> list[Engine]:
    """Every ```engine block in a brief."""
    out = []
    for k, body in enumerate(BLOCK.findall(text), 1):
        e = Engine(name=f"engine {k}")
        for raw in body.splitlines():
            line = raw.split(" #")[0].strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower()
            if low.startswith("name:"):
                e.name = line.split(":", 1)[1].strip()
            elif low.startswith("by:"):
                e.by = int(re.sub(r"\D", "", line.split(":", 1)[1]) or 0) or None
            elif low == "commander":
                e.commander = True
            elif low.startswith("tutors:"):
                e.tutors = [t.strip() for t in line.split(":", 1)[1].split(";") if t.strip()]
            elif m := REQ.match(line):
                terms = [t.strip() for t in m.group(3).split(";") if t.strip()]
                e.reqs.append(Req(n=int(m.group(2)), terms=terms, held=bool(m.group(1)), label=line))
            else:
                raise ValueError(f"engine block: can't read {line!r}")
        out.append(e)
    return out


def matches(card: Card, term: str) -> bool:
    t = term.strip()
    low = t.lower()
    if low.startswith("regex:"):
        return bool(re.search(t[6:].strip(), card.text or "", re.I))
    if low.startswith("tag:"):
        return t[4:].strip() in (card.tags or [])
    if low.startswith("type:"):
        return t[5:].strip().lower() in card.type_line.lower()
    return card.name.lower() == low or card.front_name.lower() == low


def resolve(e: Engine, deck: Deck) -> list[str]:
    """Fill each requirement's member set from the deck; return warnings (e.g. a requirement no card meets)."""
    cards = deck.cards(include_commanders=False)
    warn = []
    for r in e.reqs:
        r.members = {c.name for c in cards if any(matches(c, t) for t in r.terms)}
        if len(r.members) < r.n:
            warn.append(f"{e.name}: '{r.label}' needs {r.n} but only {len(r.members)} card(s) in the deck match")
    names = {c.name for c in cards}
    missing = [t for t in e.tutors if t not in names]
    if missing:
        warn.append(f"{e.name}: tutors not in the deck: {', '.join(missing)}")
    return warn


@dataclass
class EngineResult:
    name: str
    by: int | None
    trials: int
    online_by: dict[int, float]
    median_turn: float | None
    bottleneck: dict[str, dict[str, float]]   # requirement -> {"not drawn": share, "drawn, not deployed": share}
    members: dict[str, int]
    warnings: list[str]

    def report(self) -> str:
        L = [f"Engine '{self.name}'" + (f" (plan: online by turn {self.by})" if self.by else "")]
        L.append("  online by turn: " + "  ".join(f"T{t} {p:.0%}" for t, p in self.online_by.items()))
        L.append(f"  median turn online: {('T%.0f' % self.median_turn) if self.median_turn else 'not within 10 turns'}")
        if self.by:
            L.append(f"  missed by T{self.by}: what was missing (share of all games)")
            for label, why in self.bottleneck.items():
                L.append(f"    {label} [{self.members[label]} in deck]: not drawn {why['not drawn']:.0%}, "
                         f"drawn but not deployed {why['drawn, not deployed']:.0%}")
        for w in self.warnings:
            L.append(f"  ! {w}")
        return "\n".join(L)


def simulate(deck: Deck, e: Engine, trials: int = 10000, turns: int = 10, seed: int | None = 1) -> EngineResult:
    warnings = resolve(e, deck)
    rng = random.Random(seed)
    library_base = deck.cards(include_commanders=False)
    commanders = [x.card for x in deck.commanders if x.card]
    deck_colors = "".join(c for c in WUBRG if any(c in (cm.color_identity or "") for cm in commanders))
    ramp_cache = {id(c): ramp_effect(c) for c in library_base if not c.is_land}
    cmd = commanders[0] if commanders else None
    tutor_names = set(e.tutors)
    by = e.by or turns
    first_online: list[int] = []
    miss = {r.label: {"not drawn": 0, "drawn, not deployed": 0} for r in e.reqs}
    if e.commander:
        miss["commander"] = {"not drawn": 0, "drawn, not deployed": 0}

    def cost(c: Card):
        p = pips(c.mana_cost)
        colored = sum(int(v + 0.5) for v in p.values())
        return p, max(0, int(c.cmc) - colored), int(c.cmc)

    costs = {id(c): cost(c) for c in library_base}
    cmd_cost = cost(cmd) if cmd else None

    for _ in range(trials):
        lib = library_base[:]
        rng.shuffle(lib)
        mulls = 0
        while True:
            hand = lib[:7]
            lands = sum(c.is_land for c in hand)
            if 2 <= lands <= 5 or mulls >= 2:
                break
            mulls += 1
            rng.shuffle(lib)
        if mulls > 1:  # first mulligan free; bottom the most expensive spells
            hand.sort(key=lambda c: (not c.is_land, c.cmc))
            hand = hand[: 7 - (mulls - 1)]
        rest = lib[7:]
        sources: list[Source] = []
        cast: set[str] = set()
        seen: set[str] = {c.name for c in hand}
        cmd_cast = False
        online = 99
        missing_at_by: dict[str, str] = {}
        di = 0
        for turn in range(1, turns + 1):
            if di < len(rest):
                hand.append(rest[di])
                seen.add(rest[di].name)
                di += 1
            lands_in_hand = [c for c in hand if c.is_land]
            if lands_in_hand:
                have = set().union(*[s.colors for s in sources]) if sources else set()
                land = min(lands_in_hand, key=lambda c: (-len((set(c.produced_mana) & set(deck_colors)) - have),
                                                         _enters_tapped(c)))
                hand.remove(land)
                sources.append(land_source(land, deck_colors, turn))
            avail = sum(s.amount for s in sources if s.ready_turn <= turn)
            spent = 0

            def can(p, generic, cmc) -> bool:
                return avail - spent >= cmc and _can_pay(p, generic, sources, turn)

            if e.commander and not cmd_cast and cmd_cost and can(*cmd_cost):
                cmd_cast, spent = True, spent + cmd_cost[2]
            for c in sorted((c for c in hand if ramp_cache.get(id(c))), key=lambda c: c.cmc):
                if can(*costs[id(c)]):
                    kind, amt, cols = ramp_cache[id(c)]  # type: ignore[misc]
                    hand.remove(c)
                    cast.add(c.name)
                    spent += int(c.cmc)
                    if kind == "rock":
                        sources.append(Source(amt, cols or frozenset(deck_colors), turn))
                        avail += amt
                    else:
                        sources.append(Source(amt if kind == "dork" else 1, cols or frozenset(deck_colors), turn + 1))

            def unmet() -> list[Req]:
                out = []
                for r in e.reqs:
                    pool_ = {c.name for c in hand} if r.held else cast
                    if len(r.members & pool_) < r.n:
                        out.append(r)
                return out

            need = unmet()
            # tutor for the scarcest missing piece
            if need:
                for c in [c for c in hand if c.name in tutor_names]:
                    if can(*costs[id(c)]):
                        hand.remove(c)
                        cast.add(c.name)
                        spent += int(c.cmc)
                        r = min(need, key=lambda r: len(r.members))
                        have_names = {x.name for x in hand} | cast
                        pick = next((x for x in rest[di:] if x.name in r.members and x.name not in have_names), None)
                        if pick:
                            rest.remove(pick)
                            hand.append(pick)
                            seen.add(pick.name)
                        break
            # deploy missing cast-pieces, cheapest first
            held_names = set().union(*[r.members for r in e.reqs if r.held]) if any(r.held for r in e.reqs) else set()
            for r in unmet():
                if r.held:
                    continue
                # a card a `held` requirement wants stays in hand (a counterspell has no target on a goldfish turn)
                for c in sorted((c for c in hand if c.name in r.members and c.name not in held_names), key=lambda c: c.cmc):
                    if len(r.members & cast) >= r.n:
                        break
                    if can(*costs[id(c)]):
                        hand.remove(c)
                        cast.add(c.name)
                        spent += int(c.cmc)
            done = (not e.commander or cmd_cast) and not unmet()
            if done and online == 99:
                online = turn
            if turn == by and online == 99:
                if e.commander and not cmd_cast:
                    missing_at_by["commander"] = "drawn, not deployed"
                for r in unmet():
                    drawn = r.members & (seen | cast)
                    missing_at_by[r.label] = "not drawn" if len(drawn) < r.n else "drawn, not deployed"
        first_online.append(online)
        for label, why in missing_at_by.items():
            miss[label][why] += 1

    got = sorted(t for t in first_online if t < 99)
    res = EngineResult(
        name=e.name, by=e.by, trials=trials,
        online_by={t: sum(f <= t for f in first_online) / trials for t in range(3, turns + 1)},
        median_turn=(got[len(got) // 2] if len(got) * 2 >= trials else None),
        bottleneck={k: {w: n / trials for w, n in v.items()} for k, v in miss.items()},
        members={**{r.label: len(r.members) for r in e.reqs}, "commander": 1},
        warnings=warnings,
    )
    return res
