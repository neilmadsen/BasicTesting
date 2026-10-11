# Obeka, Splitter of Seconds — Twice-Told (Bracket 3)

Commander: Obeka, Splitter of Seconds {1}{U}{B}{R} — Legendary Creature 2/5. Menace. Whenever Obeka deals
combat damage to a player, you get that many additional upkeep steps after this phase.

**Thesis.** An additional upkeep is "your next upkeep". Rebound ("exile this as it resolves; at the
beginning of your next upkeep, you may cast it from exile without paying its mana cost") therefore fires
in the extra upkeep of the *same turn* Obeka connects. Every rebound spell cast before combat damage
resolves twice that turn, and with Cast Through Time out, so does every instant and sorcery. Upkeep spell
engines (Galvanoth casts the top card free if it's an instant or sorcery; Panoptic Mirror casts a copy of
an imprinted spell) fire once per upkeep, so two or three times on an Obeka turn. On turns she doesn't
connect, this is a normal Grixis draw-go control deck: hold up answers, trade one-for-one, draw ahead. A
spellbook control deck whose spells come back the turn the commander hits.

**Win conditions** (more than one):
1. Doubled burn to each opponent: fixed-damage sorceries and instants cast before combat damage (Fiery
   Confluence for 6 to each opponent, twice) under Cast Through Time, or rebound burn. X spells are poor
   here, because a rebound cast is "without paying its mana cost", so X = 0.
2. Obeka chip damage with evasion, plus Galvanoth and Panoptic Mirror spells, closing over turns 8–11.
3. A big draw turn into a lethal follow-up: Recurring Insight twice, then the burn above.

The builder should find the third win path's best version, or a better one.

**Engine.**
- Rebound spells: removal, card flow, tempo.
- Cast Through Time, which gives all our instants and sorceries rebound.
- Upkeep spell engines: Galvanoth, Panoptic Mirror (a Game Changer).
- Enough evasion and protection that Obeka connects: unblockable effects that aren't lands, Rogue's
  Passage-style lands, protection, and blocker removal before combat.

The order of an Obeka turn matters, and the pilot notes must spell it out:
1. Main phase 1: cast the rebound and doubled spells.
2. Combat: Obeka connects.
3. Extra upkeeps: rebounds, Galvanoth and the Mirror fire.
4. Main phase 2: sorcery-speed follow-up with whatever mana is left.

**Wants.**
- Rebound cards that are good twice: removal (Staggershock, Consuming Vapors, Blessed Reincarnation, Void
  Squall), card flow (Faithless Salvaging, Recurring Insight, Sight Beyond Sight), copy-Obeka (Quantum
  Misalignment, which makes a non-legendary token copy).
- Instants and sorceries that are good twice under Cast Through Time.
- Cheap interaction to hold up on other players' turns.
- Ways to make Obeka connect for more than 2: power pumps cast *before* combat.
- Card selection, so Galvanoth's look at the top card hits.

Browse the pool for rebound, "your next upkeep", "at the beginning of your upkeep … cast", and copy/imprint
engines; most of these cards are unplayed with this commander.

**Avoid.**
- X spells as rebound or Mirror targets (free casts give X = 0).
- Pacts cast before combat (the payment comes due in the extra upkeep, that turn).
- Cumulative upkeep, echo and "each player's upkeep" punishers.
- Sagas for their upkeep value (they tick in main phase 1).
- "The next turn's upkeep" cantrips counted as same-turn value (they don't fire early).
- Win-more piles of five-drops.

**Interaction plan.** 12+ interaction pieces, mostly instant speed: counterspells (some cheap), spot
removal that hits creatures, artifacts and enchantments, 2–3 wipes or mass bounce. Protect Obeka cheaply.
Rebound removal is our card advantage.

**Builder's change (engine spec).** Added an "Obeka turn armed" block (commander + evasion + one doubling payoff by T6), the minimum for an Obeka hit to be worth more than combat damage, and counted Sword of Wealth and Power (copies the rebound cast after a hit) and Theater of Horrors (exiles a playable card per upkeep) as doubling payoffs (plus Court of Ire, added after the gem audit), with Demonic Tutor as the tutor. The original two-payoff block stays as the stricter target.

**Bracket constraints.** B3: at most 3 Game Changers (Panoptic Mirror is one). No two-card infinite combos;
no extra-turn chains; no mass land denial.

**Targets.** Lands ~36 (some utility: Rogue's Passage), ramp ~10, card draw/selection ~10, interaction ~14
(counters ~6, removal ~6, wipes ~2), rebound/doubling engine pieces ~12, evasion/protection for Obeka ~5.
Deviate deliberately.

**User preferences.** Proxies everything; price is irrelevant. Likes control and creativity, not one-note.
The deck should have real decisions on every turn.

```engine
name: Obeka turn armed
by: 6
commander
1 of: regex:\brebound\b; Cast Through Time; Galvanoth; Panoptic Mirror; Sword of Wealth and Power; Theater of Horrors; Court of Ire
1 of: regex:can't be blocked; regex:protection from; tag:gives-hexproof; Combat Research
tutors: Demonic Tutor
```

```engine
name: Obeka doubling the spellbook
by: 6
commander
2 of: regex:\brebound\b; Cast Through Time; Galvanoth; Panoptic Mirror; Sword of Wealth and Power; Theater of Horrors; Court of Ire
1 of: regex:can't be blocked; regex:protection from; tag:gives-hexproof; Combat Research
tutors: Demonic Tutor
```

```engine
name: Interaction held up
by: 5
held 2 of: tag:counterspell; tag:spot-removal; tag:creature-removal
```
