"""Static deck analysis and a goldfish mana simulator.

The goldfish is the statistically *strong* half of the testing story. It knows
nothing about opponents or card quality, but it answers structural questions
(land count, ramp density, color sources, commander timing) with tens of
thousands of trials in a couple of seconds, which is precisely where full game
simulations are too noisy to help.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import mean

from .cards import Card, WUBRG
from .deck import BASIC_LANDS, Deck

ROLE_GROUPS: dict[str, tuple[str, ...]] = {
    "ramp": ("ramp", "mana-rock", "mana-dork", "land-ramp", "cost-reducer"),
    "card draw/advantage": ("draw", "repeatable-draw", "card-advantage", "impulsive-draw", "wheel"),
    "targeted removal": ("spot-removal", "creature-removal", "artifact-removal", "enchantment-removal", "bounce", "theft"),
    "board wipes": ("board-wipe",),
    "counterspells": ("counterspell",),
    "protection": ("protection", "gives-hexproof", "gives-indestructible"),
    "recursion": ("recursion", "reanimate"),
    "tutors": ("tutor",),
    "graveyard hate": ("graveyard-hate",),
}

# Rough targets for a 99 at brackets 2-4. They are guide rails, not law:
# a deck whose commander draws cards needs less draw, a combo deck plays
# more tutors, a stompy deck wants more ramp. Deviate on purpose.
ROLE_TARGETS = {
    "ramp": (8, 14),
    "card draw/advantage": (8, 14),
    "targeted removal": (6, 12),
    "board wipes": (1, 5),
    "protection": (1, 6),
}

_PIP = re.compile(r"\{([^}]+)\}")


def pips(mana_cost: str) -> Counter:
    c: Counter = Counter()
    for sym in _PIP.findall(mana_cost or ""):
        s = sym.upper()
        if s in WUBRG:
            c[s] += 1
        elif "/" in s:
            # hybrid & phyrexian: count each color half a pip for demand purposes
            for part in s.split("/"):
                if part in WUBRG:
                    c[part] += 0.5
    return c


def roles_of(card: Card) -> list[str]:
    tags = set(card.tags or [])
    roles = [r for r, ts in ROLE_GROUPS.items() if tags & set(ts)]
    # Scryfall's "tutor" tag includes land search (Cultivate, Sakura-Tribe Elder); that's ramp, not a tutor.
    if "tutors" in roles and ("land-ramp" in tags or re.search(r"search your library for (?:up to \w+ )?(?:a |an |two )?(?:basic )?(?:land|forest|plains|island|swamp|mountain)", card.text, re.I)):
        roles.remove("tutors")
    return roles


# --------------------------------------------------------------------------- mana model

def _enters_tapped(card: Card) -> bool:
    t = card.text.lower()
    if "enters tapped" in t or "enters the battlefield tapped" in t:
        return not any(k in t for k in ("unless", "if you control", "you may pay"))
    return False


def _add_amount(text: str) -> int:
    m = re.search(r"add ([^.]*)", text, re.I)
    if not m:
        return 0
    clause = m.group(1)
    syms = len(_PIP.findall(clause))
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    for w, n in words.items():
        if re.search(rf"\b{w} mana\b", clause, re.I):
            return max(syms, n)
    return max(syms, 1)


@dataclass
class Source:
    amount: int
    colors: frozenset[str]
    ready_turn: int


def land_source(card: Card, deck_colors: str, turn: int) -> Source:
    produced = set(card.produced_mana) & set(WUBRG)
    if not produced and "search your library" in card.text.lower():
        produced = set(deck_colors)  # fetch lands: approximate as any deck color
    ready = turn + 1 if _enters_tapped(card) or ("search your library" in card.text.lower() and "tapped" in card.text.lower()) else turn
    return Source(1, frozenset(produced), ready)


def ramp_effect(card: Card) -> tuple[str, int, frozenset[str]] | None:
    """Classify a nonland card's mana contribution for the goldfish.

    Returns (kind, amount, colors): kind in {rock, dork, land}.
    """
    t = card.text.lower()
    tags = set(card.tags or [])
    colors = frozenset(set(card.produced_mana) & set(WUBRG))
    if card.main_type in ("Creature",) and "{t}: add" in t:
        return ("dork", _add_amount(card.text), colors)
    if card.main_type in ("Artifact", "Enchantment") and "{t}: add" in t and "sacrifice" not in t.split("{t}: add")[0][-40:]:
        return ("rock", _add_amount(card.text), colors)
    if "land-ramp" in tags or re.search(r"search your library for (?:up to )?(?:a|one|two) basic land", t):
        return ("land", 1, frozenset())
    return None


def _can_pay(cost_pips: Counter, generic: int, sources: list[Source], turn: int) -> bool:
    ready = [s for s in sources if s.ready_turn <= turn]
    total = sum(s.amount for s in ready)
    need_colored = [c for c, n in cost_pips.items() for _ in range(int(n + 0.5))]
    if total < generic + len(need_colored):
        return False
    # bipartite: each colored pip needs a distinct unit of mana of that color
    units = []
    for s in ready:
        units += [s.colors] * s.amount
    match: dict[int, int] = {}

    def try_assign(p: int, seen: set[int]) -> bool:
        for u, cols in enumerate(units):
            if need_colored[p] in cols and u not in seen:
                seen.add(u)
                if u not in match or try_assign(match[u], seen):
                    match[u] = p
                    return True
        return False

    return all(try_assign(p, set()) for p in range(len(need_colored)))


@dataclass
class GoldfishResult:
    trials: int
    lands: int
    mulligans: float
    land_drop_rate: list[float]
    lands_on_bf: dict[int, float]
    mana_by_turn: dict[int, float]
    commander_turn: dict[str, float] = field(default_factory=dict)
    commander_on_curve: dict[str, float] = field(default_factory=dict)
    commander_by_plus1: dict[str, float] = field(default_factory=dict)
    commander_never: dict[str, float] = field(default_factory=dict)
    color_screw: dict[str, float] = field(default_factory=dict)
    screw_t4: float = 0.0
    flood_t7: float = 0.0
    role_access: dict[str, dict[int, float]] = field(default_factory=dict)

    def report(self) -> str:
        L = [f"Goldfish: {self.trials} trials, {self.lands} lands, avg mulligans {self.mulligans:.2f} (first one free)"]
        L.append("  land drop made on turn: " + "  ".join(f"T{i+1} {p:.0%}" for i, p in enumerate(self.land_drop_rate)))
        L.append("  avg mana available:     " + "  ".join(f"T{t} {v:.1f}" for t, v in self.mana_by_turn.items()))
        L.append(f"  mana screw (≤2 lands on T4): {self.screw_t4:.0%}    flood (≥9 lands seen by T7): {self.flood_t7:.0%}")
        for name in self.commander_turn:
            L.append(
                f"  {name}: avg first cast T{self.commander_turn[name]:.1f} | on curve {self.commander_on_curve[name]:.0%}"
                f" | by +1 {self.commander_by_plus1[name]:.0%} | not by T10 {self.commander_never[name]:.0%}"
                f" | color-blocked at +1 {self.color_screw[name]:.0%}"
            )
        if self.role_access:
            L.append("  P(have ≥1 in hand/play by turn):")
            for role, by_t in self.role_access.items():
                L.append(f"    {role:22s} " + "  ".join(f"T{t} {p:.0%}" for t, p in by_t.items()))
        return "\n".join(L)


def goldfish(deck: Deck, trials: int = 20000, turns: int = 10, seed: int | None = 1) -> GoldfishResult:
    rng = random.Random(seed)
    library_base = deck.cards(include_commanders=False)
    commanders = [e.card for e in deck.commanders if e.card]
    deck_colors = "".join(c for c in WUBRG if any(c in (cm.color_identity or "") for cm in commanders))
    n_lands = sum(1 for c in library_base if c.is_land)
    ramp_cache = {id(c): ramp_effect(c) for c in library_base if not c.is_land}
    role_names = ["ramp", "card draw/advantage", "targeted removal", "board wipes"]
    card_roles = {id(c): set(roles_of(c)) for c in library_base}

    drop_hits = [0] * 5
    bf_lands_acc: dict[int, list[int]] = {3: [], 5: [], 7: []}
    mana_acc: dict[int, list[int]] = {t: [] for t in (2, 3, 4, 5, 6, 8)}
    mull_acc = []
    cmd_first: dict[str, list[int]] = {c.name: [] for c in commanders}
    cmd_colorblock = {c.name: 0 for c in commanders}
    screw = flood = 0
    access_turns = (2, 4, 6)
    access = {r: {t: 0 for t in access_turns} for r in role_names}

    cmd_costs = []
    for c in commanders:
        p = pips(c.mana_cost)
        colored = sum(int(v + 0.5) for v in p.values())
        cmd_costs.append((c.name, p, max(0, int(c.cmc) - colored), int(c.cmc)))

    def keepable(hand: list[Card]) -> bool:
        lands = sum(1 for c in hand if c.is_land)
        cheap_ramp = sum(1 for c in hand if not c.is_land and ramp_cache.get(id(c)) and c.cmc <= 2)
        return 2 <= lands <= 5 or (lands == 1 and cheap_ramp >= 2)

    for _ in range(trials):
        lib = library_base[:]
        rng.shuffle(lib)
        mulls = 0
        while True:
            hand = lib[:7]
            if keepable(hand) or mulls >= 3:
                break
            mulls += 1
            rng.shuffle(lib)
        # London mulligan: first mulligan free in multiplayer Commander
        to_bottom = max(0, mulls - 1)
        if to_bottom:
            hand.sort(key=lambda c: (c.is_land and sum(x.is_land for x in hand) > 3, c.cmc), reverse=True)
            bottomed, hand = hand[:to_bottom], hand[to_bottom:]
        rest = lib[7:]
        mull_acc.append(mulls)
        draw_i = 0
        sources: list[Source] = []
        lands_played = 0
        lands_seen = sum(1 for c in hand if c.is_land)
        cast_cmd: dict[str, int] = {}
        seen_roles: dict[str, int] = {}
        for c in hand:
            for r in card_roles[id(c)]:
                seen_roles.setdefault(r, 0)
        for turn in range(1, turns + 1):
            if draw_i < len(rest):
                card = rest[draw_i]
                draw_i += 1
                hand.append(card)
                lands_seen += card.is_land
                for r in card_roles[id(card)]:
                    seen_roles.setdefault(r, turn)
            # land drop: prefer one adding a missing commander color, untapped first
            lands_in_hand = [c for c in hand if c.is_land]
            if lands_in_hand:
                have = set().union(*[s.colors for s in sources]) if sources else set()
                def land_key(c: Card) -> tuple:
                    new_colors = len((set(c.produced_mana) & set(deck_colors)) - have)
                    return (-new_colors, _enters_tapped(c))
                land = min(lands_in_hand, key=land_key)
                hand.remove(land)
                sources.append(land_source(land, deck_colors, turn))
                lands_played += 1
                if turn <= 5:
                    drop_hits[turn - 1] += 1
            avail = sum(s.amount for s in sources if s.ready_turn <= turn)
            spent = 0
            # commander(s) first, then ramp with leftover mana
            for name, p, generic, cmc in cmd_costs:
                if name in cast_cmd:
                    continue
                if avail - spent >= cmc:
                    if _can_pay(p, generic, sources, turn):
                        cast_cmd[name] = turn
                        spent += cmc
                    elif turn == cmc + 1:
                        cmd_colorblock[name] += 1
            ramp_in_hand = sorted((c for c in hand if ramp_cache.get(id(c))), key=lambda c: c.cmc)
            for c in ramp_in_hand:
                if c.cmc <= avail - spent:
                    kind, amt, cols = ramp_cache[id(c)]  # type: ignore[misc]
                    hand.remove(c)
                    spent += int(c.cmc)
                    if kind == "rock":
                        sources.append(Source(amt, cols or frozenset(deck_colors), turn))
                        avail += amt
                    elif kind == "dork":
                        sources.append(Source(amt, cols or frozenset(deck_colors), turn + 1))
                    else:
                        basics = frozenset(deck_colors)
                        sources.append(Source(1, basics, turn + 1))
            if turn in mana_acc:
                mana_acc[turn].append(sum(s.amount for s in sources if s.ready_turn <= turn))
            if turn in bf_lands_acc:
                bf_lands_acc[turn].append(lands_played)
            if turn == 4 and lands_played <= 2:
                screw += 1
            if turn == 7 and lands_seen >= 9:
                flood += 1
        for name, *_ in cmd_costs:
            cmd_first[name].append(cast_cmd.get(name, 99))
        for r in role_names:
            first = seen_roles.get(r)
            for t in access_turns:
                if first is not None and first <= t:
                    access[r][t] += 1

    res = GoldfishResult(
        trials=trials,
        lands=n_lands,
        mulligans=mean(mull_acc),
        land_drop_rate=[h / trials for h in drop_hits],
        lands_on_bf={t: mean(v) for t, v in bf_lands_acc.items()},
        mana_by_turn={t: mean(v) for t, v in mana_acc.items()},
        screw_t4=screw / trials,
        flood_t7=flood / trials,
        role_access={r: {t: v / trials for t, v in by.items()} for r, by in access.items()},
    )
    for name, p, generic, cmc in cmd_costs:
        firsts = cmd_first[name]
        cast = [f for f in firsts if f < 99]
        res.commander_turn[name] = mean(cast) if cast else float("nan")
        res.commander_on_curve[name] = sum(f <= cmc for f in firsts) / trials
        res.commander_by_plus1[name] = sum(f <= cmc + 1 for f in firsts) / trials
        res.commander_never[name] = sum(f == 99 for f in firsts) / trials
        res.color_screw[name] = cmd_colorblock[name] / trials
    return res


# --------------------------------------------------------------------------- static report

def summary(deck: Deck) -> str:
    main = deck.cards(include_commanders=False)
    nonland = [c for c in main if not c.is_land]
    lands = [c for c in main if c.is_land]
    mdfc_lands = [c for c in nonland if "//" in c.type_line and "Land" in c.type_line.split("//")[1]]
    types = Counter(c.main_type for c in main)
    L = [f"{deck.title or 'Deck'} — {deck.size()} cards ({len(deck.commanders)} commander(s))"]
    L.append("  commander(s): " + ", ".join(e.name for e in deck.commanders))
    L.append("  types: " + ", ".join(f"{t} {n}" for t, n in types.most_common()))
    L.append(f"  lands: {len(lands)} ({sum(c.name in BASIC_LANDS for c in lands)} basic)"
             + (f" + {len(mdfc_lands)} MDFC land backs" if mdfc_lands else ""))
    if nonland:
        L.append(f"  avg mana value (nonland): {mean(c.cmc for c in nonland):.2f}")
    curve = Counter(min(int(c.cmc), 7) for c in nonland)
    L.append("  curve: " + "  ".join(f"{'7+' if k == 7 else k}:{curve.get(k, 0)}" for k in range(0, 8)))
    # color demand vs supply
    demand: Counter = Counter()
    for c in nonland:
        demand.update(pips(c.mana_cost))
    for e in deck.commanders:
        if e.card:
            demand.update({k: v * 3 for k, v in pips(e.card.mana_cost).items()})  # commander weighs extra
    supply = Counter()
    deck_cols = set(deck_colors_of(deck))
    for c in lands:
        for col in set(c.produced_mana) & deck_cols:
            supply[col] += 1
        if not c.produced_mana and "search your library" in c.text.lower():
            for col in deck_colors_of(deck):
                supply[col] += 1
    tot = sum(demand.values()) or 1
    L.append("  color pips vs land sources: " + "  ".join(
        f"{col} {demand[col] / tot:.0%} of pips / {supply[col]} lands" for col in WUBRG if col in deck_cols))
    role_counts: dict[str, list[str]] = {r: [] for r in ROLE_GROUPS}
    untagged = []
    for c in nonland:
        rs = roles_of(c)
        for r in rs:
            role_counts[r].append(c.name)
        if not rs:
            untagged.append(c.name)
    L.append("  roles (from Scryfall tagger; a card can fill several):")
    for r, names in role_counts.items():
        tgt = ROLE_TARGETS.get(r)
        flag = ""
        if tgt and len(names) < tgt[0]:
            flag = f"  ← below typical {tgt[0]}-{tgt[1]}"
        elif tgt and len(names) > tgt[1]:
            flag = f"  ← above typical {tgt[0]}-{tgt[1]}"
        L.append(f"    {r:22s} {len(names):3d}{flag}")
    L.append(f"    (no role tag / theme cards: {len(untagged)})")
    gcs = [c.name for c in deck.cards() if c.game_changer]
    L.append(f"  game changers ({len(gcs)}): {', '.join(gcs) or '—'}")
    return "\n".join(L)


def deck_colors_of(deck: Deck) -> str:
    m = deck.color_identity_mask()
    return "".join(c for i, c in enumerate(WUBRG) if m & (1 << i))


def sample_hands(deck: Deck, n: int = 5, draws: int = 3, seed: int | None = None) -> str:
    """Opening hands plus the next few draws, for eyeball review ("would I keep this?")."""
    rng = random.Random(seed)
    lib = deck.cards(include_commanders=False)
    out = []
    for i in range(n):
        rng.shuffle(lib)
        hand, nxt = lib[:7], lib[7:7 + draws]
        lands = sum(c.is_land for c in hand)
        out.append(f"Hand {i + 1} ({lands} lands):")
        for c in sorted(hand, key=lambda c: (not c.is_land, c.cmc, c.name)):
            out.append(f"   {c.name} {c.mana_cost or ''}".rstrip())
        out.append("   then draws: " + ", ".join(c.name for c in nxt))
    return "\n".join(out)
