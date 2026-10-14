# Obeka, Splitter of Seconds: Many Mornings (Bracket 3)

Commander: Obeka, Splitter of Seconds {1}{U}{B}{R}, Legendary Creature, Ogre Warlock 2/5, menace.
"Whenever Obeka deals combat damage to a player, you get that many additional upkeep steps after this phase."

**Thesis.** The strategy is *more upkeeps*, not one engine. The deck spreads upkeep value across several
resources: cards, bodies, control, a little mana, and Obeka's own power. Every Obeka hit then pays out on
whatever is on the board, and no single removal spell ends the engine. Each upkeep permanent must be worth
its slot at 1× (on turns she doesn't connect) and decisive at 4–8×. Around it sits a real Grixis control
shell: cheap instant-speed interaction, scaling board answers, and blockers that grow on our turns.

Role research: `decks/obeka-splitter-of-seconds/roles/` (README.md plus four shortlists). Read the README
and use the shortlists as the candidate pool. They're oracle-checked.

**Timing facts (they decide card choice).**
- Obeka's extra upkeeps come after combat and before main phase 2. Buffs gained in them help the *next*
  attack, not this one.
- Paradox Haze's and The Ninth Doctor's upkeeps come before combat.
- Mana empties between steps; Treasure persists.
- "Your next upkeep" fires the same turn.
- Upkeep *costs* multiply like benefits (life, sacrifices, cumulative upkeep).
- "Each player's upkeep, that player…" symmetric punishers hit only us in our extra upkeeps.
- "Each opponent's upkeep" never fires in ours.
- An upkeep permanent cast in main phase 1 fires that same turn if Obeka connects.

**Multiply the multiplier (the user asked for this explicitly).** Trigger doublers make one hit worth 2–3×
the upkeeps:
- **Roaming Throne naming Warlock** (Obeka is an Ogre Warlock) doubles her natively: no hub needed.
- Strionic Resonator copies her trigger, or any upkeep trigger at 1x. Gogo, Master of Mimicry and Mirror
  Room // Fractured Realm are the slower options.
- Double strike gives two damage triggers: Hard-Won Jitte, Psychotic Fury, Lizard Blades, Blacksmith's
  Talent.
- Doublers stack: Throne + double strike means four triggers; a 2-damage hit is eight upkeeps.
- *Decided in rev 4:* no Wizard package. Psychic Paper or Arcane Adaptation would make her a Wizard for Wizard's
  Staff and Harmonic Prodigy, but that is four slots, two of them pure enablers, for what Throne does alone.
  Avarice Amulet's draw is a trigger *of the equipped creature*, so Throne doubles it; the Rings' counters are
  triggers of the Equipment, so doublers don't touch them.

Include a real doubler package: about 3–5 cards across doublers and double strike, chosen for cost and
redundancy.

**Roles and a starting slot budget** (deviate deliberately and say why in notes.md):

| Role | Slots | Lead candidates (see roles/) |
|---|---|---|
| Lands | 35 | 1–2 storage lands (Bottomless Vault, Dwarven Hold, Sand Silos gain a counter each upkeep while tapped), Rogue's Passage |
| Ramp | ~8 | conventional rocks; upkeep Treasure is a bonus (only 6 in the pool) |
| Connect: power / evasion / protection / haste | 6–7 | Wrecking Ball Arm (base 7/7; power ≤2 can't block), Avarice Amulet (+2, vigilance, draw each upkeep), Ring of Valkas / Evos Isle / Xathrid, Feast on the Fallen, Swiftfoot Boots (hexproof, not shroud), Silent Arbiter, Sword of Light and Shadow, Conqueror's Flail |
| More upkeeps + doublers | 4–6 | Paradox Haze, The Ninth Doctor, Roaming Throne (Warlock), Strionic Resonator, Hard-Won Jitte, Psychotic Fury |
| Upkeep card advantage | 5–6 | **Plargg and Nassari (core: 2 free spells per upkeep, no mana needed; only the exile is symmetric)**, Bonehoard Dracosaur, Theater of Horrors, Tamiyo's Journal, Court of Locthwain, Phyrexian Arena, Avarice Amulet |
| Upkeep bodies (weighted to defence) | 5–6 | Chronozoa, Ophiomancer, Dragonmaster Outcast, Virtue of Persistence, Mechanized Production + Thopter Assembly |
| Upkeep control | 5–6 | Court of Ire, Recantation, Legacy's Allure, Lilting Refrain, Argentum Masticore, Sphere of Annihilation, Midnight Banshee, Coercive Portal |
| Instant-speed interaction (not upkeep) | 11–13 | ~5 counters (cheap), ~4 spot removal that hits creatures and artifacts/enchantments, 2–3 alpha-strike answers (Aetherize, Aetherspouts, Blasphemous Act, Toxic Deluge) |

**Density target.** About 18–22 upkeep engines in the 99, so that 2–3 are on board by T5. Cards that fill
two roles are preferred, for example:
- Avarice Amulet: connect + draw;
- Bonehoard Dracosaur: draw + Treasure + blocker;
- Chronozoa: bodies + defence + lightning rod;
- Recantation, Legacy's Allure, Lilting Refrain: control that charges per upkeep and is cashed at instant
  speed.

**Win conditions** (at least two, from different resources):
1. **Commander damage:** a doubler plus Rings or Feast on the Fallen, or Wrecking Ball Arm, make Obeka
   lethal in 2–3 hits.
2. **A conversion module:** pick one or two of:
   - Mechanized Production on Thopter Assembly: 5/5 fliers each upkeep, and eight Assemblies win at upkeep.
     Order Production's trigger first.
   - Endless Evil or Extravagant Replication on Dragonmaster Outcast.
   - Court of Ire and Theater of Horrors damage per upkeep.
3. **Attrition:** out-card the table behind counters and sweepers.

**Known weaknesses to cover** (from piloted games and the threat model in `brainstorm.md`):
- **Go-wide boards (Edgar's black Vampires, Giada's Angels) killed us around round 10.** Midnight Banshee
  misses black creatures; Crumbling Ashes fails on +1/+1-counter boards. Prefer scaling answers that don't
  care: Recantation, Sphere of Annihilation, Blasphemous Act, Toxic Deluge, Aetherspouts, and blockers that
  grow on our turns.
- **Menace means two chump blockers stop Obeka.** Real evasion matters (Wrecking Ball Arm, Brotherhood Regalia,
  Thassa, Silent Arbiter, Rogue's Passage).
- **Monarch and initiative invite attacks.** Don't rely on the monarch. A second Court is fine once one is in: it
  doesn't make us monarch more often (rev 5).
- **Life budget:** no Dark Confidant-style engines, no Demonic Pact, no mandatory mass draw (Mind Unbound,
  The Magic Mirror).

**Avoid.**
- Shroud equipment (Greaves, Whispersilk): it blocks our own equips and tricks.
- Fixed power caps (Access Tunnel).
- Symmetric "each player's upkeep" punishers.
- Cumulative-upkeep cards except Braid of Fire with Leyline Tyrant.
- Win-more piles of 5–6-drop upkeep permanents. Keep the curve honest: most engines at 2–4 mana.

**Bracket 3.** At most 3 Game Changers, no two-card infinite combos, no extra-turn chains, no mass land
denial.

**User preferences.** Proxies everything; price is irrelevant. Likes control and creativity, and decks with
real decisions every turn and more than one way to win. Gems need one-line justifications.

```engine
name: Obeka armed
by: 6
commander
2 of: regex:at the beginning of (your|each) upkeep; Roaming Throne; Strionic Resonator; Paradox Haze; The Ninth Doctor
1 of: Wrecking Ball Arm; Silent Arbiter; Sword of Light and Shadow; Rogue's Passage; Swiftfoot Boots; regex:can't be blocked
tutors: Demonic Tutor
```

```engine
name: Two upkeep engines on board
by: 5
2 of: regex:at the beginning of (your|each) upkeep
```

```engine
name: Doubled hit
by: 7
commander
1 of: Roaming Throne; Strionic Resonator; Gogo, Master of Mimicry; Hard-Won Jitte; Psychotic Fury; Lizard Blades; Blacksmith's Talent
tutors: Demonic Tutor
```

```engine
name: Board answer held
by: 7
held 1 of: Blasphemous Act; Toxic Deluge; Aetherize; Aetherspouts; Recantation; Sphere of Annihilation; Cyclonic Rift; Damnation; Delayed Blast Fireball
tutors: Demonic Tutor
```

```engine
name: Interaction held up
by: 5
held 2 of: tag:counterspell; tag:spot-removal; tag:creature-removal
```

```engine
name: Card-advantage engine on board
by: 5
1 of: Bonehoard Dracosaur; Plargg and Nassari; Taigam, Sidisi's Hand; Theater of Horrors; Court of Ire; Virtue of Persistence // Locthwain Scorn; Rhystic Study; Court of Locthwain; Midnight Clock; Mystic Remora; Sword of Fire and Ice; Avarice Amulet
tutors: Demonic Tutor
```
