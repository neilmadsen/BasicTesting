# Muldrotha Groundskeeper (Bracket 3): notes

## Plan

The land lane is the engine. Fetch lands, horizon lands, cycling duals, Memorials,
Blighted Fen, Ifnir Deadlands and the channel lands are spells that cost a land
drop. The deck replays them every turn in three ways:

- **Graveyard-land permission:** Mole Man, Ramunap, Icetill Explorer, Ancient
  Greenwarden, Titania, Nature's Force (Forest-typed lands only), Life from the
  Loam, and finally Muldrotha.
- **Extra land drops:** Azusa, Dryad, Exploration, Oracle, Loot, Wayward
  Swordtooth, Aesi, Icetill.
- **Free put-onto-battlefield effects:** Undergrowth Recon, Blossoming Tortoise and
  Lumra return lands **tapped**. Titania, Protector of Argoth returns one untapped.

A replayed fetch land gives two landfall triggers and puts one land into the
graveyard. The payoffs are split across those two events:

- **Landfall:** Scute Swarm, Greensleeves, Sapling Nursery, Avenger, Field of the
  Dead, Ob Nixilis, Mole Man, Springheart Nantuko, Tracker, Tatyova, Aesi, Lotus
  Cobra, Nissa, Provisioner.
- **A land hitting the graveyard or being sacrificed:** Titania, Protector of
  Argoth; Scouring Swarm; The Gitrog Monster. The land-sacrifice outlets are
  Zuran Orb, Elvish Reclaimer, Sylvan Safekeeper, Springbloom Druid and Gitrog's
  upkeep.

**How it wins:**

- A token army from landfall (insects, badgers, treefolk, 5/3 Elementals,
  zombies, plants) that swings once Craterhoof or Avenger's counters land.
- Ob Nixilis draining 3 per land, which gets through blockers and fogs.
- A Scapeshift turn with Titania plus Field, Avenger, Greensleeves or Sapling
  Nursery on board.

A wipe doesn't end the plan, because the engine lives in the lands.

**Rules note (fixed in brief.md).** Playing a land from the graveyard with Muldrotha
uses your normal land play; she gives permission, not an extra drop. That is why
the list has 8 extra-drop sources and 4 put-onto-battlefield effects. Muldrotha
allows only one graveyard land per turn, while Ramunap, Mole Man and Icetill let
every available land drop come from the graveyard.

**Key turns.**
- T1–2: mana (Birds, Delighted Halfling, Mox Diamond, Sol Ring, Lotus Cobra,
  Sakura-Tribe Elder, Nature's Lore, Three Visits) or an engine piece (Exploration,
  Elvish Reclaimer, Springheart Nantuko, Life from the Loam). Crack a fetch land
  every turn.
- T3: Azusa, Dryad, Mole Man, Ramunap, Undergrowth Recon, Six or Scute Swarm.
- T4–5: a payoff (Titania, Greensleeves, Sapling Nursery, Scouring Swarm, Gitrog,
  Tatyova).
- T5–6: Muldrotha. From there every turn is one graveyard land plus one creature,
  artifact and enchantment cast from the graveyard.

**Mulligan.**
- Keep 3–5 lands that include an untapped green source, plus at least one of: an
  extra land drop, a graveyard-land piece, or 1–2 MV ramp (9 in the deck).
- Keep a 2-lander only with 1–2 MV ramp and an untapped green source.
- Mulligan 0–1 landers, 6–7 landers, and two tapped lands with nothing to cast
  before turn 3.
- Expect about 55–60% of 7-card hands to be keeps (see Testing). The first
  mulligan is free.

## Pilot notes

**Trigger order.** With Ancient Greenwarden out, one fetch land can make 8–12
triggers. Work through them in this order:

1. **Mana triggers first.** Resolve Lotus Cobra and Nissa before anything that
   needs paying for, such as Springheart Nantuko's {1}{G} copy.
2. **Field of the Dead** checks for 7+ land names both when it triggers and when it
   resolves. The deck has 35 names, so after turn 6 this is automatic.
3. **Ob Nixilis:** choose a target for each trigger. Each resolution adds three
   counters.
4. **Draw triggers last** (Tatyova, Tracker clues, Aesi), after Icetill's mill
   trigger. That way you see the most before you choose which land to replay.
5. **Crack the new fetch land while its triggers are on the stack** only if you need
   the mana or a Titania token now. Otherwise let the triggers resolve and crack it
   at end of turn.

**Rules and counting details.**
- **Nissa, Resurgent Animist** digs on the *second resolution of her trigger* each
  turn. With Greenwarden, the first land's doubled trigger is already the second
  resolution.
- **Scouring Swarm** copies itself only if 7+ land cards are in the graveyard when
  its trigger resolves. Muldrotha, Lumra, Loam and Recon keep emptying the
  graveyard, so expect mostly 1/1 fliers. If you want copies, hold the graveyard
  lands for a turn.
- **Undergrowth Recon, Tortoise and Lumra return lands tapped.** A returned fetch
  land can't be cracked that turn without Amulet of Vigor, and a returned Memorial
  can't be activated. Amulet is what makes those lines immediate.
- **Boseiju, Otawara and Takenuma have no basic land types.** No fetch land finds
  them, and Titania, Nature's Force can't replay them. Once channelled, they're
  ordinary graveyard lands for Muldrotha, Ramunap or Mole Man.
- **Kaya's Ghostform** saves Muldrotha only if you let her stay in the graveyard (or
  exile) instead of moving her to the command zone. Otherwise the Aura's trigger
  has nothing to return.
- **The deck has 15 fetchable lands** (7 typed duals, 2 typed cycling duals, 6
  basics), so the fetch lands run dry around turn 10. Keep cracking them anyway:
  the sacrifice still triggers Titania, Scouring Swarm and Gitrog, and the fetch
  land itself is still a landfall trigger.
- **Mox Diamond:** discard a fetch land or a cycling land. Muldrotha recasts Mox
  from the graveyard, which turns a spare land in hand into mana plus a graveyard
  land for later.

## Key cards and lines

1. **Fetch loop.** Mole Man or Ramunap plus one extra drop: play a fetch land and
   crack it, then replay it from the graveyard and crack it again. That is four
   landfall triggers and two lands to the graveyard per turn: two Titania 5/3s, two
   Scouring Swarm fliers, two Gitrog draws, 2–4 Clues or 1/1s.
2. **Undergrowth Recon + Amulet of Vigor.** Every upkeep a fetch land comes back
   and Amulet untaps it: crack it at once for two free landfall triggers before our
   land drop. Without Amulet it comes back tapped and gets cracked next turn, so
   the steady state is still one extra landfall pair a turn.
3. **Horizon lands + Blossoming Tortoise.** Tortoise makes land abilities cost {1}
   less, so Nurturing Peatland and Waterlogged Grove draw for 0 every turn once
   they loop. Memorial to Genius costs {3}{U}.
4. **Amulet of Vigor + Memorials.** A replayed Memorial to Genius (draw two) or
   Memorial to Folly (regrow a creature) untaps and fires the same turn. Amulet
   also untaps the Triome, the three tapped typed duals, Tranquil Thicket, and
   basics from Fabled Passage and Springbloom Druid.
5. **Elvish Reclaimer → Field of the Dead.** With 7+ land names, every land entering
   makes a 2/2. Ancient Greenwarden doubles it.
6. **Channel first, play later.** Boseiju (artifact, enchantment or nonbasic land),
   Otawara (bounce) and Takenuma (mill 3, regrow) are instant-speed spells from
   hand that end up as lands in the graveyard to replay.
7. **Scapeshift for N** with Titania plus Field, Avenger, Greensleeves or Sapling
   Nursery out: N 5/3s plus N landfall triggers (the new lands enter tapped). The
   sacrificed lands come back through the graveyard lane.
8. **Craterhoof Behemoth** after a turn of token making. Muldrotha can recast it
   from the graveyard if it dies.

## Gems (non-staple picks and why they beat the obvious card)

EDHREC's Muldrotha page (2,567 B3 decks) lists every card above about 6% inclusion.
"Not on the page" means under that. Global EDHREC rank shows how rare a card is
everywhere.

| Card | Why it's here instead of the staple |
|---|---|
| **Mole Man, Moloid Master** (#5,628) | Ramunap's graveyard-land permission at the same 3 MV, plus a 1/1 per landfall. Ramunap only enables; Mole Man also builds the army. |
| **Undergrowth Recon** (#4,967) | Crucible needs your land drop. Recon puts a land from the graveyard into play (tapped) every upkeep without one, so it stacks with Muldrotha and extra drops. With Amulet, the returned fetch land cracks at once. |
| **Scouring Swarm** (#5,669) | A flier for every land we sacrifice (fetch lands, horizon lands, Memorials, Reclaimer, Zuran Orb): 2–4 a turn. It copies itself only with 7+ lands in the graveyard, and the deck keeps emptying the graveyard, so treat it as a steady flier engine, not Scute Swarm growth. |
| **Greensleeves, Maro-Sorcerer** (#2,764) | Rampaging Baloths' role (a creature per landfall, 3/3 vs 4/4) one mana cheaper, on a */* body equal to our lands, with protection from planeswalkers and Wizards. |
| **Sapling Nursery** (#4,406) | A 3/4 reach per landfall. 12 Forest-typed lands (all of them with Dryad) usually make it cost 3–5. Its exile ability makes Forests and Treefolk indestructible through a wipe, and Muldrotha recasts it. It replaced Squirrel Wrangler. |
| **Lumra, Bellow of the Woods** (#1,130) | Splendid Reclamation (7% here) is a one-shot sorcery. Lumra mills 4, returns every land in the graveyard (tapped), and is a creature Muldrotha recasts after it dies. |
| **Titania, Nature's Force** (#4,069) | A 5/3 per Forest entering: 12 Forest-typed lands and 11 fetch lands make it 1–3 a turn, and she replays Forest-typed lands from the graveyard. It pairs with Titania, Protector of Argoth: one triggers on a land entering, the other on a land leaving. |
| **Ob Nixilis, the Fallen** (#1,956) | The only landfall payoff that skips combat: 3 life per land, targeted. Four landfall triggers is 12 damage a turn. |
| **Blossoming Tortoise** (#3,301) | On entering and on attack: mill 3 and return a land (tapped). It also makes every land activation {1} cheaper (horizon draws for 0, Demolition Field for {1}, Memorial to Genius for {3}{U}). |
| **Elvish Reclaimer** (#2,064) | A repeatable land tutor on a 1-drop (Field of the Dead, Memorials, Bojuka Bog), and it grows to 3/4. Expedition Map is a one-shot. |
| **Amulet of Vigor** (#1,276) | 9 of our lands enter tapped, and so does everything Recon, Tortoise and Lumra return. Amulet makes those lands usable the turn they arrive: the Recon fetch land cracks at once, and a replayed Memorial fires the same turn. |
| **Springheart Nantuko** (#698 overall, not on Muldrotha's page) | A 2-drop that makes a 1/1 per landfall at once. Late, bestowed on Avenger, Scute Swarm or Tortoise, each land is {1}{G} for a token copy. |
| **Zuran Orb** (#911) | A free, instant-speed land-sacrifice outlet: Titania, Scouring Swarm and Gitrog on demand, in response to wipes or land destruction. The life buys turns against aggro. It's also the piece to cut if the table objects to the Lumra loop (see Bracket). |
| **Terastodon** | Up to three noncreature permanents destroyed. Pointed at our own spent lands it makes three 3/3s, and the lands return through the land lane. Muldrotha recasts it. |
| **Scapeshift** | Not Valakut here. Sacrificing N lands and fetching N is 2N triggers across Titania, Scouring Swarm, Gitrog, Field, Avenger, Greensleeves, Nursery and Ob Nixilis. |
| **Memorial to Genius / Memorial to Folly / Blighted Fen / Ifnir Deadlands** | Lands that sacrifice for draw-two, regrowth, an edict or two -1/-1 counters. Muldrotha turns each into a repeatable spell that costs no card. |
| **Festering Thicket / Rain-Slicked Copse** (#1,909 / #3,254) | Typed cycling duals (Swamp Forest, Forest Island): every fetch land finds them, and they cycle when drawn late. They replace plain tapped duals. |

**Archetype staples that are still rare for Muldrotha:** Avenger of Zendikar, Scute
Swarm, Lotus Cobra, Tireless Tracker, Aesi, Ancient Greenwarden, Oracle of Mul Daya,
Titania, Protector of Argoth and Craterhoof are all below EDHREC's page threshold for
this commander. They are standard in lands decks, though, so they aren't marked GEM.
Birds of Paradise, Delighted Halfling and Mox Diamond are plain staples, included
for turn-1 speed.

## Critique round

A deck-critic review (which would play the deck at B3 as is, given pre-game
disclosure of the Lumra loop) raised six points. I took all of the swaps:

| Change | Why (my judgement) |
|---|---|
| Crop Rotation → **Mox Diamond** (Game Changer for Game Changer) | Crop Rotation is a one-shot the Forge AI can't use. Mox is turn-0 mana, the discarded land is fuel for the land lane, and Muldrotha recasts Mox. The sim showed our first spell by T2 in only 14 of 24 games. |
| Redrock Sentinel → **Birds of Paradise** | Redrock was a slow 3-drop that cost 1 mana plus a land per card; I had wrongly said it netted mana. Birds fixes the T1 hole and green pips. |
| Crucible of Worlds → **Delighted Halfling** | Crucible was the 7th graveyard-land permission and did nothing alone. Halfling is a 1-drop that casts our 15 legendary spells (Muldrotha included) in any color, uncounterably. |
| Squirrel Wrangler → **Sapling Nursery** | Wrangler was low impact and weak for the Forge AI. Nursery was my own "best card left out". |
| Island → Forest; Underground Sea → **Underground Mortuary** | 14 of 39 lands made no green against 76% green pips. Green sources go from 25 to 27 and blue from 21 to 19 (blue is 9% of pips). Mortuary is a Swamp Forest, so it's fetchable, Nursery counts it, and its surveil feeds the graveyard. I didn't add Dryad Arbor: Nantuko + Arbor + a mana-per-landfall creature is a turn 4–5 infinite. |
| Rules fixes | Recon, Tortoise and Lumra return lands tapped. The channel lands have no basic types. Memorial to Genius is {3}{U} with Tortoise. Ghostform on Muldrotha needs the command-zone move declined. Redrock doesn't net mana. All are corrected above and in deck.txt. |

**Keep rate, rechecked.** 16 hands at seed 11: 8 clear keeps, 2 borderline (a Mox +
Loam 2-lander, a top-heavy 3-lander), 6 mulligans (two 0–1 landers, four 2-landers
with no cheap ramp). My earlier "8 of 12" was generous, and the critic's ~6 of 16 is
closer. It's structural: at 39 lands, 27% of 7-card hands have exactly 2 lands.
Going to 40 lands only moves 3–5-land hands from 56% to 58%, so I kept 39 and put 3
more one-mana accelerants in instead.

## Testing

**Goldfish** (`./edh analyze`, 10k trials, final list, 39 lands):
- Muldrotha is cast on **T5.1** on average (v1: 5.4): on curve (T6) **89%** (v1:
  84%), by T7 95%, not by T10 0%.
- T4 screw (≤2 lands) 5%; flood (≥9 lands seen by T7) 4%. Average mana is 5.0 on
  T4 and 7.1 on T6.
- Ramp tags at 25 (typical 8–14). That is deliberate: extra land drops are the
  engine, not just acceleration.
- Color sources: G 27 / B 24 / U 19 lands, against 76% / 15% / 9% of pips.
- Keep rate: about 55–60% of 7-card hands (see Critique round).

**Forge sim, final list** (32 games vs the B3 gauntlet, `sims/20260923-052548-b3/`;
the card list matches `candidates/deck-v3-simmed.txt`):
- **Won 3/32 = 9%, 95% CI 3–24%** (baseline 25%). There were 4 timeouts/draws.
- Average game 9.6 rounds. We win on round 8.3 and die on round 9.8. Losses: 21
  to damage or drain, 3 to poison (Atraxa).
- Commander cast in **69%** of games (v1: 58%), first on round 6.8.
- The first spell came by our turn 1 in 12/32 games, by turn 2 in **22/32 = 69%**
  (v1: 14/24 = 58%), and by turn 3 in 29/32. The critique's early-turn fix worked
  as intended.
- New counter: the AI used 1.9 spells and 2.5 lands per game from our own
  graveyard. The top ones were Bloodstained Mire ×10, Haywire Mite ×8, Marsh Flats
  ×7, Blighted Fen ×7 and Swamp ×7. The land lane runs, but the AI uses it
  modestly: a human replays 1–3 lands a turn once the engine is up.
- Y'shtola won 7/10 again, and Atraxa 3/7 (poison).
- In a representative loss (pod 3, game 3) we cast Muldrotha on T5 and rebuilt
  after three sweepers (Blasphemous Act, Living Death and a third), casting
  Muldrotha three times, Avenger twice and Greenwarden three times. Edgar Markov
  and Sauron still won the race on damage. The deck survives wipes but is slow to
  convert its board into damage when the Forge AI pilots it.

**Earlier list** (v1, 24 games, `sims/20260923-044839-b3/`): 4/24 = 17%, CI 7–36%.
The two CIs overlap almost entirely, and the pods differed (v3 also met Atraxa,
Ms. Bumbleflower and Sephiroth). **The sims don't show a difference between the
versions.** The goldfish, which is precise, shows v3 is faster (T5.1 vs T5.4, 89% vs
84% on curve). I kept v3 on that evidence and on the reasoning in Critique round.

**Never cast (v3)** (6):
- Toxic Deluge, Sylvan Library, Beast Within, Scapeshift, Sylvan Safekeeper: Forge
  flags them `ai_cannot_play`, so the sim is blind to them. All stay; they're good
  cards in human hands.
- Icetill Explorer: cast in 6/24 v1 games, so this is variance. It stays.
- Survival of the Fittest (`ai_weak`) was cast this time. Forge still undervalues
  it, Elvish Reclaimer, Pernicious Deed and Demolition Field.

**Caveats.** The Forge AI misplays this archetype in specific ways:
- It rarely taps sacrifice-lands for value, and uses about 2.5 graveyard lands a
  game.
- It can't use Scapeshift or Zuran Orb.
- It doesn't prioritize Muldrotha, or attack with a wide token board.

So read the sims as "the deck functions, survives wipes and isn't broken", not as a
win-rate estimate. With 56 games across two versions, the honest summary is "at or
somewhat below par against Forge", with wide error bars.

## Bracket

`./edh validate deck.txt --bracket 3`: **PASS**. Game Changers (3): Field of the Dead,
Survival of the Fittest, Mox Diamond. Commander Spellbook tags the deck "Powerful
(≈bracket 3+)" and lists the combos below as info. No REVIEW items were raised, but
these need an explicit answer:

- **Game Changer choice.** Field of the Dead is a win condition this deck makes
  trivially (35 land names). Survival finds whichever engine creature is missing,
  and the creatures it discards are castable through Muldrotha. Mox Diamond turns
  a spare land into turn-0 mana, and Muldrotha recasts it. I passed on Crop
  Rotation (cut in the critique round), Gaea's Cradle and Worldly Tutor.
- **Pre-game disclosure (required): the Lumra loop.** *Lumra + Springheart Nantuko
  (bestowed on Lumra) + Zuran Orb + Lotus Cobra, Nissa or Tireless Provisioner*:
  - It's a genuine infinite: each Lumra copy returns every land, the lands' landfall
    mana pays for the next copy, and Zuran Orb sends the lands back.
  - With Field of the Dead it makes unbounded tokens. With Ob Nixilis out it kills
    the table outright (and mills us 4 per loop, so stop once they're dead).
  - Survival tutors three of the four pieces, so it's easier to assemble than
    "four specific cards" suggests. It needs 10–11 mana across the pieces, so it's
    realistically turn 7+.
  - That fits B3's allowance for late, multi-card combos, and it isn't the plan. The
    deck wins through tokens without it.
  - **Tell the table before the game. If they object, cut Zuran Orb** (Sylvan
    Safekeeper, Elvish Reclaimer and Springbloom Druid remain as land-sacrifice
    outlets) and the loop is gone.
- **Other Spellbook entry:** *Springbloom Druid + Springheart Nantuko + Amulet of
  Vigor* (3 cards, MV 6), which Spellbook calls "near-infinite". Each Druid copy nets
  a basic, and it stops when the six basics run out: a burst of tokens and lands,
  not a kill.
- **Combos removed:** Golgari Rot Farm + Amulet + Nantuko + extra-drop infinites
  (v1, turn 5–6 possible) were cut with Rot Farm. Dryad Arbor stays out, and so
  does the Gitrog + Dakmor Salvage combo.
- **Recurring land destruction.** Demolition Field is the deck's only land
  destruction. It hits only nonbasic lands, the victim gets a basic, and we get
  one too. Recurring it answers utility lands (an opposing Cradle, Field or Maze);
  it doesn't lock anyone's mana. Strip Mine and Wasteland were left out on purpose.
- **Recurring Bojuka Bog** exiles one opponent's graveyard every turn Muldrotha is
  out. That is strong against a graveyard deck, but it is interaction, not a lock.
- **Speed.** The goldfish puts Muldrotha on T5.1 on average. The token board takes
  over around turns 6–8. Apart from the disclosed late loop there's no
  deterministic kill, so the deck sits at the strong end of B3.

## Swaps considered

- **Rampaging Baloths** for Greensleeves or Titania, Nature's Force: a bigger token
  per land, one more mana.
- **Squirrel Wrangler / Redrock Sentinel** (cut in the critique round): both are
  land-sacrifice engines, tokens and draw respectively. They're good in a slower
  meta, weak in Forge.
- **Crucible of Worlds** (cut): the one graveyard-land permission that survives a
  creature wipe. Bring it back over Delighted Halfling if your table wipes a lot.
- **Hedge Shredder** (24% on EDHREC): milled lands go straight into play. Strong
  with Six, Tortoise, Icetill and Loam's dredge, but the deck already has 25 ramp
  pieces.
- **Case of the Locked Hothouse**: a ninth extra land drop, and once solved it casts
  creatures and enchantments off the top.
- **Gaea's Cradle** over Mox Diamond as the third Game Changer, if your table is
  slower.
- **More land-lane utility:** Hidden Nursery (discover 4 for 5), The Hunter Maze
  (draw for {1}{G}), Khalni Garden (a 0/1 every replay), Skemfar Elderhall
  (-2/-2 plus two 1/1s), Yavimaya Hollow (repeatable regeneration). The Hunter Maze
  over Counterspell is the swap I'd make first if you want a 40th land.
- **Tatyova, Steward of Tides**: at 7+ lands each landfall animates a land into a
  3/3 flying haste attacker. Evasive and fast, but a wipe then costs lands.
- **Counterspell → Mystic Snake or Arcane Denial**: easier on blue mana. There
  are now 19 blue sources and no basic Island.
- **Rejected:**
  - Dryad Arbor: a Nantuko infinite.
  - Golgari Rot Farm: a combo piece.
  - Strip Mine / Wasteland: a soft land lock with recursion.
  - Glacial Chasm: a Game Changer, and a lock.
  - Dakmor Salvage: Gitrog infinite.
  - Horn of Greed / Rites of Flourishing: symmetric, and opponents get the cards.
  - Roil Elemental: UUU on a green base.
  - Worm Harvest / Vengeful Regrowth: slow sorceries Muldrotha can't recast.
  - Druid Class: the lexical screen's #1 pick. Lifegain landfall is not a plan.
