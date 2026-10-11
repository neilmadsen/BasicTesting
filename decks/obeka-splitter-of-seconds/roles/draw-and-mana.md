# Obeka roles: card advantage and mana on upkeep

Scope: the UBR + colorless legal pool. I read in full the slice where the rules text has
`at the beginning of (your|each|each player's) upkeep` (738 cards). I also read the
202-card slice with other upkeep wording (`next upkeep`, `enchanted creature's controller`,
rebound, "activate only during your upkeep"). Jev greps for upkeep Treasure, upkeep mana and
untap, upkeep land ramp, and upkeep draw/tutor turned up nothing the regex had missed. Every
pick below was checked against `./edh card`.
Obeka % is the share of Obeka's 17,881 EDHREC decks. "--" means not on its list.

**E** = the number of extra upkeeps per turn (Obeka's combat damage, usually 2–3). A trigger
on "your upkeep" fires **1+E** times on our turn.

★ = top pick for the sub-role. GEM = good fit and under 5% inclusion.

---

## Role A: card advantage on upkeep

Pool counts:

| Sub-role | Count |
|---|---|
| Pure draw | about 52 (45 draw cards, plus 5 wheels or loots, plus 2 tribal reveal cards) |
| Draw batteries and Clue makers | 7 |
| Impulse | 25, plus 4 that free-cast from the graveyard or exile |
| Tutors | 5 |
| Regrowth of other cards | 7 |
| Self-recursion | 13 |

Timing: impulse cards that say "play it this turn" work fine in main phase 2. Lands work
too, if the land drop is still unused.

### A1. Pure draw (card goes to hand)

| Card | MV | Obeka % | Per upkeep | Cost per upkeep | Also fills |
|---|---|---|---|---|---|
| ★ Phyrexian Arena | 3 | 49% | 1 card | 1 life | -- |
| ★ Super Intelligence | 1 | 26% | 1 card. The Aura triggers in "the upkeep of enchanted creature's controller", so put it on our own creature | none | -- |
| ★ Avarice Amulet (GEM) | 4 | 8% | 1 card | none. If the creature dies, an opponent gets the Equipment | Put it on Obeka: +2 power means more upkeeps; vigilance keeps her back to block |
| ★ Baleful Force (GEM) | 8 | -- | 1 card ("each upkeep", so it also draws on opponents' turns) | 1 life | 7/7 body |
| ★ Taigam, Sidisi's Hand (GEM) | 5 | -- | Look at 3, take 1, the other 2 go to the graveyard | We skip our draw step | Removal: {B}, tap, exile X cards from the graveyard: -X/-X. Fills the graveyard for regrowth |
| Staff of Nin (GEM) | 6 | -- | 1 card | none | Pings 1 damage each turn |
| Seymour Flux (GEM) | 5 | -- | optional: 1 card and a +1/+1 counter | 1 life | Body that keeps growing |
| Eye of Vecna (GEM) | 2 | -- | optional: 1 card | {2} and 2 life. Thran Turbine can pay the {2} | -- |
| Twilight Prophet | 4 | 77% | 1 card plus a drain of X. Needs the city's blessing (10 permanents) | none | Flier; gains life |
| Seizan, Perverter of Truth | 5 | -- | 2 cards. Triggers on each player's upkeep, so opponents also draw 2 a turn | 2 life | 6/5 |
| Graveborn Muse | 4 | -- | X cards, where X is our Zombies (at least 1, itself) | X life | -- |
| Struggle for Project Purity | 4 | 6% | 3 cards; each opponent draws 1 | Gives opponents cards | Mode choice. Not in Brotherhood mode, but the Enclave mode is a defensive deterrent |
| Indulgent Tormentor | 5 | 50% | A card, or the opponent pays 3 life or sacrifices a creature | none | Flier |
| Dark Confidant, Dark Tutelage, Darkstar Augur | 2/3/3 | -- | 1 card | Life equal to the card's MV. At 1+E upkeeps that is about 8–12 life a turn | Too dangerous here |
| Mind Unbound, The Magic Mirror | 6/9 | 7%/-- | 1, 2, 3, 4… cards. The draw is mandatory | Decking. One Obeka turn draws about 10, and the next about 26 | Use only as a one-shot that we then bounce or sacrifice |

Each-upkeep and each-player's-upkeep cards that draw for us on our extra upkeeps:

- Baleful Force
- Seizan
- Super Intelligence
- Ghirapur Orrery (3 cards if our hand is empty)
- Asylum Visitor (1 card if our hand is empty)
- Midnight Clock (adds a counter)
- Oath of Scholars
- Gate to the Aether and Braids (cards onto the battlefield; see B5)

### A2. Impulse draw (exile, then play it)

| Card | MV | Obeka % | Per upkeep | Cost / window | Also fills |
|---|---|---|---|---|---|
| ★ Bonehoard Dracosaur | 5 | 34% | 2 cards, plus a Treasure (if one is nonland) or a 3/1 (if one is a land) | Play them this turn | 5/5 flier with first strike; ramp |
| ★ Court of Locthwain | 4 | 61% | 1 card from the opponent's library, kept indefinitely. While we are monarch, each trigger lets us cast one exiled card free | none | Monarch; theft |
| ★ Theater of Horrors (GEM) | 3 | -- | 1 card, kept indefinitely. Playable on our turn if an opponent lost life, and Obeka's hit guarantees that | none | Ping for {3}{R} |
| ★ Jacob Hauken / Hauken's Insight (GEM) | 2 (+6 to transform) | -- | 1 face-down card, kept indefinitely | Free play only once per turn | The front face loots |
| ★ Tavern Brawler (GEM) | 3 | 7% | 1 card, plus +X/+0 on Obeka | Play it this turn | The pump from the normal upkeep makes the next hit bigger, which means more upkeeps |
| Rassilon, the War President | 5 | -- | 1 card, kept indefinitely | 2 life | Conspire copies |
| Outpost Siege (Khans) | 4 | -- | 1 card | Play it this turn | -- |
| Plargg and Nassari | 5 | 62% | Up to 2 free spells (from opponents' libraries too) | An opponent picks one card to deny | -- |
| Stolen Strategy, Laughing Jasper Flint, The Ruinous Powers | 5/3/4 | 7%/28%/-- | 1 card from each opponent (Jasper: X cards from one target opponent) | Play it this turn | -- |

Also in the pool:

- Urabrask, Heretic Praetor
- Count on Luck
- Wild Wasteland (skips our draw step)
- Charred Foyer
- Vance's Blasting Cannons
- Visions of Phyrexia
- Headliner Scarlett
- Triple Triad (13%)
- Xanathar, Guild Kingpin (9%)
- Galvanoth
- Nassari, Dean of Expression

### A3. Tutors and batteries

| Card | MV | Obeka % | Per upkeep | Notes |
|---|---|---|---|---|
| ★ Tamiyo's Journal | 5 | 20% | 1 Clue | At 1+E ≥ 3 that is one tutor every turn, or {2}-draws |
| ★ Profane Tutor | 0 (suspend {1}{B}) | 36% | 1 time counter | Suspend 2 usually resolves in an extra upkeep on the same turn |
| Barrin's Codex (GEM) | 4 | -- | 1 page counter (optional) | {4}: draw X. Grows 1+E a turn |
| Midnight Clock | 3 | 27% | 1 hour counter ("each upkeep") | Mana rock. Draws 7 sooner |
| Obsessive Pursuit (GEM) | 2 | -- | 1 Clue | 1 life per upkeep. Pumps attackers |
| Kyren Archive | 3 | -- | 1 face-down card (optional) | {5}, discard hand: take all of them |
| Curse of Misfortunes | 5 | -- | 1 Curse onto the battlefield | Only in a Curse build |

### A4. Regrowth to hand

| Card | MV | Obeka % | Per upkeep | Notes |
|---|---|---|---|---|
| ★ Palace Siege (Khans) | 5 | 40% | 1 creature card | The Dragons mode drains 2 per upkeep instead |
| ★ Exalted Flamer of Tzeentch (GEM-ish) | 4 | 7% | 1 random instant or sorcery | Pings each opponent per spell |
| Oversold Cemetery | 2 | -- | 1 creature card | Needs 4 or more creature cards in the graveyard |
| Fantastic Elasticity (GEM) | 3 | -- | Rebound fires in the first extra upkeep | Bounce a permanent, or regrow an instant or sorcery, twice in one turn |
| Master of Death | 3 | -- | Returns itself from the graveyard | 1 life. Surveil 2 each time it enters |

Rebound note: "your next upkeep" is the first extra upkeep, so a main-phase-1 rebound spell
recasts on the same turn. Recurring Insight (6 MV, --) does this: draw about 5, then about 5
more after combat. Cast Through Time gives rebound to every instant and sorcery we cast.

---

## Role B: mana on upkeep

**Are there many? No.** Only **6** cards in the whole legal pool make Treasure on upkeep.
**2** more add pool mana that lasts to end of turn, and **0** make Gold or Powerstones on
upkeep. That is 8 sources of direct, persistent upkeep mana, against about 52 upkeep draw
cards. Counting batteries, untappers and land ramp, about 30 cards touch mana on upkeep, and
fewer than half of those are good.

Which kinds matter to Obeka:

- **Matter:** Treasure (B1), persistent pool mana (B1b), and batteries (B3), because the
  stored counters survive and cash out any time.
- **Also matter:** untap (B4) and land ramp (B5), because the untapped or new permanent is
  still there in main phase 2.
- **Do not matter on their own:** emptying mana (B2). It only pays for instants and
  abilities inside that upkeep, unless we run a mana keeper (Leyline Tyrant, Ozai, Horizon
  Stone).

### B1. Upkeep Treasure and persistent mana (6 + 2)

| Card | MV | Obeka % | Per upkeep | Cost per upkeep | Also fills |
|---|---|---|---|---|---|
| ★ Smaug the Magnificent | 4 | 13% | 1 Treasure | none | Flier with haste. Its attack deals damage equal to our Treasures to any target |
| ★ Bonehoard Dracosaur | 5 | 34% | 1 Treasure if a nonland is exiled (plus 2 impulse cards) | none | Also an A2 pick |
| ★ Ultimate Green Goblin (GEM) | 3 | -- | 1 Treasure | Discard a card (mandatory). With an empty hand it is free, and it still makes the Treasure | 5/4; discard outlet |
| ★ Generous Plunderer | 2 | 35% | 1 Treasure (optional) | Target opponent gets a tapped Treasure | Menace. Its attack deals damage equal to the defender's artifacts, so the gifts come back as damage |
| Tempting Contract (GEM) | 4 | -- | 1 Treasure for each opponent who accepts | Opponents get Treasure too | Politics |
| Descent into Avernus | 3 | 29% | X Treasures to every player. X goes 2, 4, 6… because each upkeep adds 2 counters | X damage to every player. At 1+E=4 that is 2+4+6+8 = 20 damage to everyone in one turn | It is a symmetric kill switch, not ramp |
| ★ Karn, Legacy Reforged (GEM) | 5 | -- | {C} per artifact, kept **until end of turn** | Only for artifact spells and abilities | 6 artifacts × 4 upkeeps is about 24 mana in main phase 2. It pays for Clues, equip and Barrin's Codex |
| Rousing Refrain | 5 (suspend {1}{R}) | 47% | {R} per card in the target opponent's hand, kept until end of turn | none | Re-suspends with 3 counters, so under Obeka it recurs about every turn |

### B2. Upkeep mana that empties (2, plus 3 keepers)

| Card | MV | Obeka % | Per upkeep | Use |
|---|---|---|---|---|
| ★ Braid of Fire | 2 | 10% | {R} × age counters, so 1, 2, 3, 4… | Cumulative upkeep that pays us. It grows every upkeep, but if we skip paying once it is sacrificed. Alone it only feeds instants. With a keeper it is the biggest mana engine in the pool |
| Thran Turbine (GEM) | 1 | -- | {C}{C}, can't be spent to cast spells | Pays upkeep costs and abilities: Eye of Vecna's {2}, cracking Clues, echo, Barrin's Codex |
| ★ Leyline Tyrant (GEM keeper) | 4 | -- | -- | We don't lose unspent **red** mana. Braid of Fire mana then stacks across upkeeps and turns. 4/4 flier; its death trigger is a Fireball |
| Ozai, the Phoenix King (keeper) | 6 | -- | -- | Unspent mana becomes red instead of emptying. 7/7 with trample and haste |
| Horizon Stone (keeper) | 5 | -- | -- | Unspent mana becomes colorless. Assume Thran Turbine's "not for spells" restriction stays on that mana; check the rules before relying on it |

Chaos Moon only changes what Mountains tap for; reject it.

### B3. Charge and battery permanents (11)

| Card | MV | Obeka % | Per upkeep | Cash-out |
|---|---|---|---|---|
| ★ Replicating Ring | 3 | 76% | 1 night counter | At 8 counters it makes 8 Ring tokens. Under Obeka that is turn 2–3 after casting, not turn 8. Taps for mana meanwhile |
| ★ As Foretold | 3 | 83% | 1 time counter | One free spell per turn of MV ≤ counters. Works as mana |
| ★ Sand Silos / Bottomless Vault / Dwarven Hold (GEM, land slots) | 0 | -- | 1 storage counter, only while the land is tapped | Tap it in main phase 1 to empty it. The extra upkeeps reload it, so it yields about E mana every turn while costing a land slot |
| ★ Lotus Blossom | 2 | 9% | 1 petal (optional) | Sacrifice: X mana of one color, at any time including main phase 2 |
| Shrine of Boundless Growth (GEM) | 3 | -- | 1 charge | Sacrifice: {C} per counter |
| Lotus Bloom / Mox Tantalite / Sol Talisman | 0/0/0 | 7%/14%/24% | 1 time counter | Suspend 3, so they arrive in 1–2 turns. Lotus Bloom's 3 mana can be saved for main phase 2 |
| Aether Vial | 1 | 8% | 1 charge (optional) | Puts a creature into play at instant speed. Mana-equivalent for creatures |

### B4. Upkeep untap (6 that touch mana)

| Card | MV | Obeka % | Per upkeep | Notes |
|---|---|---|---|---|
| ★ Tidal Force (GEM) | 8 | -- | Tap or untap one target permanent ("each upkeep") | Our turn: untap a land or rock for main phase 2. Their turns: tap a blocker or a mana source. Fills control |
| Rising Waters (GEM, creative lock) | 4 | -- | Each player untaps 1 land in their upkeep | Lands never untap normally. Opponents get 1 land a turn; we get 1+E. Fills control |
| Mist of Stagnation (creative lock) | 5 | -- | Untap one permanent per card in our graveyard | With a full graveyard, each extra upkeep untaps our whole board for main phase 2 |
| Mana Vault | 1 | -- | Pay {4} to untap a rock that makes {C}{C}{C} | Loses mana each time; reject |
| Forsaken City | land | -- | Exile a card from hand to untap | Costs a card each time; reject |
| Sands of Time | 4 | -- | Untaps what is tapped and taps what is untapped | Also taps our untapped stuff; reject |

Dominus of Fealty (9%) and Frenzied Fugue steal and untap a permanent until end of turn. That
belongs to the theft role, not ramp. About 14 more cards untap only themselves (Brass Man and
similar) and don't matter here.

### B5. Upkeep land ramp (3, all symmetric; none search the library for lands)

| Card | MV | Obeka % | Per upkeep | Notes |
|---|---|---|---|---|
| ★ Braids, Conjurer Adept | 4 | 36% | Put an artifact, creature or land from hand onto the battlefield | Each player's upkeep, so opponents get it too, but we get it 1+E times |
| Gate to the Aether | 6 | 8% | Reveal the top card; if it is an artifact, creature, enchantment or land, put it onto the battlefield | Each player's upkeep. Also card advantage |
| Wild Evocation | 6 | -- | A random card from hand: a land goes onto the battlefield, anything else is cast free | Each player's upkeep. Chaotic |

---

## Notable rejects

- **Demonic Pact.** Its four modes run out on the fourth upkeep, which is often turn 1 of
  Obeka connecting, and the last mode is "you lose the game".
- **Mind Unbound / The Magic Mirror** as permanent engines. The draw is mandatory and decks us
  in about 2 Obeka turns.
- **Dark Confidant / Dark Tutelage / Darkstar Augur.** They cost life equal to the card's MV,
  1+E times a turn.
- **Psychic Vortex.** Its cumulative upkeep draws more each upkeep, but at end step we
  sacrifice a land and discard our hand.
- **Visions of Phyrexia.** Its Powerstone comes at end step, once a turn, so Obeka doesn't
  multiply it.
- **Mana Vault.** Paying {4} to untap gets back {3}.
- **Timesifter.** Each upkeep runs an extra-turn lottery that is symmetric and random. Fun,
  but not this role.
- **Cards that draw "at the beginning of the next turn's upkeep"** (Arcane Denial, the
  Baubles, Foresight and others). That trigger never lands in our extra upkeeps.
- **Sagas** (Rite of Belzenlok). Lore counters arrive in main phase 1, not the upkeep.
