# Obeka brainstorm: what the upkeep pool can do

This is a walk through the legal pool sliced by what the upkeep trigger *does* (`./edh pool`, plus a compact
slicer). It's a brainstorm: it deliberately chooses nothing. Percentages are the share of Obeka's EDHREC decks
running a card; `--` means unlisted (rarely or never played with her).

## What Obeka actually multiplies

The evidence comes from the upkeep tally of 23 piloted games (`research/upkeep_ledger.py`). It credits
everything our seat triggered in her extra upkeeps:
- **Rebound recasts:** 1 in 11 games. Rebound only moves a second cast earlier; it adds no cards.
- **Per-upkeep permanents** did the work: Ring of Evos Isle 102 triggers, Court of Ire 38, Gisa 34, Enslave 31,
  Panoptic Mirror 14.
- **The best game** (119 extra upkeeps, a win) was a Ring snowball.

So the useful question for any card is: **per extra upkeep, what does it produce, and does it compound?**

**Kinds of value an extra upkeep can produce:**
1. **Repeat value:** one more trigger of something good (Court of Ire, Phyrexian Arena, Creeping Bloodsucker).
2. **Compounding into the next hit:** the trigger makes Obeka bigger, so the next connection buys more upkeeps
   (the Rings, the Undercity Forge, Sword of Truth and Justice).
3. **Compounding within the turn:** the trigger increases the number of triggers in the next upkeep (Endless
   Ranks, Followed Footsteps on an upkeep creature, Extravagant Replication copying an engine, Chronozoa).
4. **Thresholds:** counters race toward a payoff that's checked *at the upkeep*, so each extra upkeep is both a
   tick and a check (Darksteel Reactor, Mechanized Production, Triskaidekaphile).
5. **Timing only:** effects that would happen anyway, just sooner (rebound, suspend, vanishing). Worth
   something, but not card advantage. Vanishing and suspend are interesting mainly when the delayed effect is
   the point (Chronozoa, Reality Acid).

**Timing facts that shape every family:**
- The extra upkeeps come **after combat and before main phase 2**. So "play it this turn" impulse draws, Treasure,
  and anything the upkeeps put in hand are all usable in main phase 2.
- Pumps, equips and haste granted in those upkeeps don't help this turn's attack.
- **Mana empties between steps:** mana made in an upkeep (Braid of Fire, Karn) is for instants and abilities
  in that upkeep only. Treasure persists.
- **"Your next upkeep" fires this turn; "the next turn's upkeep" doesn't.** Pacts cast before combat come
  due in the extra upkeep.
- **The wording decides who an extra upkeep belongs to.** There are four cases:
  - "At the beginning of **your** upkeep": fires in every extra upkeep. This is the whole commander.
  - "At the beginning of **each** upkeep" (Magmatic Force, Tidal Force, Baleful Force, Ophiomancer, Feast on
    the Fallen, Midnight Clock): already fires on all four players' turns; Obeka adds more.
  - "At the beginning of **each player's** upkeep, **that player** …": in our extra upkeeps, *that player*
    is us, every time. Symmetric cards stop being symmetric. A boon (Seizan, Gate to the Aether, Braids,
    Conjurer Adept) becomes ours alone on an Obeka turn. A punisher (Smokestack, The Abyss, Necrogen Mists,
    Sulfuric Vortex) hits only us. See family R.
  - "At the beginning of **each opponent's** upkeep" (Mogis, Iron Maiden, Persistent Constrictor, the
    hellbent punishers): never multiplied. These are fine filler for a slug deck, but Obeka does nothing for
    them.
- **Steals made in the extra upkeeps can't attack**, but they can be tapped for abilities or mana, or sacrificed.

## Multipliers on the multiplier (more upkeeps per hit)

Every family below gets stronger with these, so they're a shared layer, not a strategy:
- **Power:** Ring of Evos Isle, Ring of Xathrid and Ring of Valkas (+1 counter per upkeep: compounding), Sword
  of Wealth and Power, Sword of Truth and Justice, and the Undercity Forge (two counters per venture).
- **Double strike:** Lizard Blades. Each strike is a separate combat-damage trigger.
- **Trigger doublers:**
  - Roaming Throne (name Ogre or Warlock; 11%) and Wizard's Staff (equipped Obeka's triggers trigger twice;
    8%) make her trigger happen twice.
  - Strionic Resonator, Lithoform Engine, Gogo, Adric and Peter Parker's Camera copy it.
  - Two doublers on a 2-power Obeka is eight upkeeps.
- **Upkeeps without combat:** Paradox Haze (40%) and The Ninth Doctor (22%, who adds an upkeep whenever he
  untaps). These make every per-upkeep card work on turns she doesn't connect.
- **Evasion that scales with the theme:** Call of the Ring (16%) tempts us every upkeep, so the Ring completes
  in one Obeka turn. Obeka as Ring-bearer:
  - can't be blocked by creatures with greater power;
  - loots when she attacks;
  - makes any creature that blocks her get sacrificed at end of combat;
  - drains each opponent for 3 whenever she hits.

## Strategy families

Each family: the core cards, how it uses Obeka, and what worries me. None is chosen.

### A. Alternate wins checked at upkeep
- **Core:**
  - Mechanized Production (62%): a token copy of an artifact every upkeep, winning at eight. On a Sol Ring it's
    also +2 mana per copy.
  - Darksteel Reactor (27%): wins at 20 counters.
  - Triskaidekaphile: wins with exactly 13 cards in hand at an upkeep, and draws at instant speed, so the extra
    upkeeps are several checks with draw windows between them.
  - Revel in Riches (10 Treasures), Liliana's Contract (four Demons), Mortal Combat (20 creatures in our
    graveyard), Hellkite Tyrant (20 artifacts).
- **Uses Obeka:** as ticks and checks. Proliferate (Flux Channeler, Inexorable Tide, Tekuthal) speeds the
  counters.
- **Worry:** each win condition is a single card that removal blanks. It wants redundancy: two or three wins
  plus tutors. That could be a "wins you didn't see coming" deck, which suits the table-reading taste.

### B. Group slug: the table bleeds every upkeep
- **Core:** Creeping Bloodsucker (67%), Subversion, Ill-Gotten Inheritance, Quakebringer (2 damage to each
  opponent each upkeep, and *opponents can't gain life*, which answers Giada), Court of Ambition, Bloodgift
  Demon, Scrawling Crawler.
- **Uses Obeka:** repeat value. It works even when she rarely connects, because the natural upkeep ticks too.
- **Worry:** symmetric damage (Descent into Avernus) needs a life buffer. The deck stalls against heavy
  lifegain unless Quakebringer is out.

### C. Nekusar with Obeka as the wheel
- **Core:** symmetric draw every upkeep (Scrawling Crawler, Stormfist Crusader, Kumena's Awakening) or
  opponents-only draw (Master of the Feast, Struggle for Project Purity's Brotherhood mode, which also draws us
  one per card they draw). Draw punishers in our colours (Underworld Dreams-style).
- **Uses Obeka:** each extra upkeep is a round of opponent draws, and each draw costs them life.
- **Worry:** it feeds opponents cards. That's political: it can be framed as generous until it isn't.

### D. Post-combat impulse and playing other people's decks
- **Core:**
  - Count on Luck, Outpost Siege (Khans), Visions of Phyrexia, Urabrask, Charred Foyer, Bonehoard Dracosaur
    (34%) and Wild Wasteland: exile the top card, playable this turn.
  - Court of Locthwain (61%), Stolen Strategy and Laughing Jasper Flint: cast *opponents'* cards with any mana.
- **Uses Obeka:** each extra upkeep is a card playable in main phase 2. That's real card advantage, and the
  creative version steals the table's spells.
- **Worry:** mana in main phase 2. It wants Treasure makers (Tempting Contract, Generous Plunderer) and cheap
  spells.

### E. Spellbook done right: free, recurring and cheaper spells per upkeep
- **Core:**
  - Recurring spells: Charmbreaker Devils and Exalted Flamer of Tzeentch return an instant or sorcery to hand
    each upkeep. That's card advantage, not rebound's timing.
  - Free casts: Galvanoth casts the top card, Panoptic Mirror casts its imprinted spell, Theater of Horrors.
  - Cheaper spells: Mindsplice Apparatus (one oil counter per upkeep, so spells get {1} cheaper each upkeep).
  - Card selection to set up the top of the library (Thassa, Brainstorm).
- **Uses Obeka:** repeat value plus within-turn compounding (Mindsplice), leading into a refuelled main
  phase 2.
- **Worry:** Galvanoth hits only on instants and sorceries; the Devils' return is random. Both need a
  high spell density.

### F. Zombie compounding
- **Core:** Endless Ranks of the Dead (new Zombies equal to half our Zombies each upkeep), The Scarab God
  (each opponent loses X, X = our Zombies, each upkeep), Graveborn Muse (draw X), Dreadhorde Invasion, Archdemon
  of Unx, Tombstone Stairwell.
- **Uses Obeka:** within-turn compounding into a drain that scales with the count. The most explosive loop
  in the pool, and nearly unplayed with her.
- **Worry:** it's tribal, so card quality varies. It's weak to sweepers, though the Zombies regrow.

### G. Copying the engine (the quadratic turn)
- **Core:** Extravagant Replication (65%) and Followed Footsteps / Endless Evil copy an upkeep engine:
  Dragonmaster Outcast (78%; a 5/5 Dragon per upkeep with six lands), Creeping Bloodsucker, Courts, Skyline
  Despot.
- **Uses Obeka:** the number of triggers grows each upkeep, so a turn's value grows roughly with the square
  of the upkeep count.
- **Worry:** the most crowd-adjacent family. The creative twist is *what* gets copied.

### H. Chronozoa and time
- **Core:**
  - Chronozoa: vanishing 3; when it dies with no counters, it becomes two copies. Exponential fliers on
    Obeka's clock.
  - Reality Acid (vanishing removal that resolves in one Obeka turn), Keldon Marauders, Deadly Grub.
  - Suspend payoffs: Aeon Chronicler draws per counter removed, Watcher of Hours surveils per counter.
- **Uses Obeka:** timing only, but here the delayed effect *is* the value (Chronozoa doubling, removal
  resolving).
- **Worry:** a small card pool. Probably a package, not a deck.

### I. Reanimating creatures with enter-the-battlefield effects every upkeep
- **Core:**
  - Dawn of the Dead returns a creature with haste each upkeep and exiles it at end of turn. Sacrifice it
    before then and it's back in the graveyard for the next upkeep.
  - Payoffs: Gray Merchant, Shriekmaw, Mulldrifter.
  - Heavier versions: Sheoldred, Whispering One, Portal to Phyrexia (from any graveyard), Virtue of
    Persistence, Gisa.
  - Sacrifice outlets.
- **Uses Obeka:** repeat value with real card advantage, because each reanimation is a fresh
  enter-the-battlefield trigger.
- **Worry:** graveyard hate. It needs self-mill or creatures that die, which overlaps J.

### J. Forced sacrifice as fuel (aristocrats)
- **Core:**
  - Cultist of the Absolute: our commander gets +3/+3, flying and deathtouch, but we sacrifice a creature
    each upkeep. Obeka becomes a 5/8 flier with menace hitting for five upkeeps.
  - Eldrazi Monument, Smothering Abomination (draw per sacrifice), Demonic Taskmaster, Greater Harvester.
  - Token feed: Bitterblossom, Bitterbloom Bearer, Court of Embereth, Ophiomancer.
  - Blood Artist-type payoffs.
- **Uses Obeka:** repeat value. The forced sacrifices are the engine, not a cost.
- **Worry:** running out of fodder ends the deck.

### K. The Undercity (initiative)
- **Core:** take the initiative (Caves of Chaos Adventurer 27%, Rilsa Rael 32%, Tomb of Horrors Adventurer 17%,
  Passageway Seer, Aarakocra Sneak, Sarevok's Tome, Loot Dispute); Dungeon Delver doubles room abilities.
- **Uses Obeka:** we venture every upkeep. Forge rooms grow her (compounding), Trap deals 5, and completion
  arrives in a turn or two (Tomb of Horrors Adventurer then copies spells twice).
- **Worry:** the initiative moves whenever an opponent damages us. That's political: we can choose when to
  take it back.

### L. The Ring tempts you
- **Core:** Call of the Ring, Nazgûl, Fiery Inscription, There and Back Again, Ringsight.
- **Uses Obeka:** completes the Ring in one turn. That's evasion for a 2-power commander, plus loot and 3
  damage to each opponent per hit, with Nazgûl counters as a bonus.
- **Worry:** a package, not a deck. Probably the best evasion layer for several families.

### M. Empty hand and madness
- **Core:**
  - Discard engines: Rotting Regisaur (a 7/6 for 3 that discards each upkeep), Ultimate Green Goblin (discard,
    make a Treasure), Cunning Lethemancer.
  - Wheels: Forgotten Creation, Case of the Crimson Pulse, Psychic Vortex (cumulative-upkeep draws 1/2/3).
  - Madness payoffs; graveyard recursion (Palace Siege, Khans).
- **Uses Obeka:** repeat value. Discard becomes casting, at instant speed in upkeep windows.
- **Pool check:** it isn't thin.
  - 60 madness cards are legal, many of them interaction: Big Game Hunter, Fiery Temper, Terminal Agony, Dark
    Withering, Alms of the Vein, Avacyn's Judgment, Circular Logic. Obsessive Search, Call to the Netherworld
    and Gisa's Bidding provide card flow and bodies.
  - 66 discard payoffs, the best of which are per-discard damage and bodies:
    - Magmakin Artillerist (damage to each opponent per discard) and Glint-Horn Buccaneer;
    - Cryptcaller Chariot (Zombies);
    - Bone Miser, Containment Construct, Currency Converter, Monument to Endurance, Tinybones.
  - Free discard outlets let us cast madness cards at instant speed inside an upkeep.
- **The engine piece found later: Ghirapur Orrery.** Under it, each player's upkeep draws three if that player
  has no cards in hand. Empty the hand at instant speed during one extra upkeep (madness, outlets, instants),
  and the next extra upkeep draws three more. A wheel per upkeep, and it's unplayed with Obeka.
  - Asylum Visitor and Hollowborn Barghest reward the same state.
  - Rotting Regisaur's forced discard keeps us empty.
- **The kill line, found while describing M: Forgotten Creation + Magmakin Artillerist.** In each of our
  upkeeps, the Creation may discard the whole hand and draw that many. The Artillerist deals damage to each
  opponent equal to the number of cards discarded. With a hand of five and a 3-damage hit, that's four
  upkeeps × 5 = 20 to each opponent, and the hand is refreshed each time. It's not infinite, so it's
  Bracket 3 legal. Without Obeka it's still about 5 damage a turn and a full filter.
  - Every madness card in the discarded hand triggers, and Containment Construct makes every discarded card
    playable this turn. Both are limited by the mana we kept open.
- **Worry:** the Orrery's condition is an intervening "if". The hand must already be empty *as the upkeep
  begins*, so emptying it has to happen in the previous step. Opponents with empty hands draw three in their
  upkeeps too: it's a gift to aggro decks.

### N. Hand control into recurring removal
- **Core:** strip hands (Court of Ambition, Honden of Night's Reach, Cunning Lethemancer, Indulgent Tormentor),
  then recurring removal that returns at our upkeep when we have more cards or they're hellbent (Exile into
  Darkness, Death of a Thousand Stings, Rekindled Flame).
- **Uses Obeka:** an edict or burn *every upkeep* once the condition holds. A control deck that's genuinely
  built around her.
- **Worry:** the conditions need upkeep; symmetric discard hurts us too.

### O. One-sided board wipes that grow
- **Core:** Midnight Banshee (a −1/−1 counter on each *nonblack* creature per upkeep; Obeka is black, so she's
  spared), Crumbling Ashes (destroy a creature with a −1/−1 counter each upkeep), Plague Spitter (1 damage to
  each creature and player per upkeep: shreds tokens), Contagion Engine.
- **Uses Obeka:** repeat value as a scaling sweeper. It directly answers the Edgar and Giada boards we lost to.
- **Worry:** our own nonblack creatures. Build black, or around the asymmetry.

### P. Theft for value, not attacks
- **Core:** Frenzied Fugue and Dominus of Fealty (steal each upkeep; tap the steal for mana or abilities, or
  sacrifice it), Puca's Mischief (swap each upkeep), Conjured Currency, Legacy's Allure, Virtue of Persistence.
- **Uses Obeka:** repeat value. Steals in the post-combat upkeeps fuel main phase 2 and feed sacrifice outlets.
- **Worry:** mostly temporary steals, so it needs sacrifice outlets or a reason to use the stolen permanent now.

### Q. Demons racing to a win
- **Core:** Blood Speaker (sacrifice at upkeep to tutor a Demon; it returns whenever a Demon enters),
  Liliana's Contract (wins at upkeep with four Demons), upkeep Demons (Bloodgift Demon, Indulgent Tormentor,
  Lord of the Pit, Demonic Taskmaster, Abhorrent Overlord), Demonic Pact.
- **Uses Obeka:** each extra upkeep is another tutor and another check.
- **Worry:** a cute thematic hybrid of A and J. The quality of its Demons decides it.

### R. The active-player clause: symmetric cards that turn one-sided
- **Idea:** "At the beginning of each player's upkeep, that player …" gives every player one trigger per round.
  On an Obeka turn, we take two or three more, and opponents take none. The table accepts a symmetric card
  more readily than a one-sided one, and Obeka quietly cashes it in.
- **Boons the pool offers (almost all unplayed with her):**
  - Seizan, Perverter of Truth: each player loses 2 and draws 2 in their upkeep, so an Obeka hit for 3 is
    six cards for us. It's also a 6/5 Demon for family Q.
  - Braids, Conjurer Adept (36%, the one the crowd found): a free artifact, creature or land from hand per
    upkeep.
  - Gate to the Aether: the top card goes onto the battlefield if it's a permanent. Pair it with scry.
  - Wild Evocation: a random card from hand is cast free (lands go onto the battlefield).
  - Infernal Genesis: mill one, create Minions equal to its mana value.
  - Oath of Ghouls, Oath of Mages and Oath of Scholars: a regrowth, a ping, or a new hand of three, each
    conditional on being behind someone.
  - **Rite of the Raging Storm:** every player gets a 5/1 trample, haste Lightning Rager each upkeep, and
    those Ragers can't attack us. The opponents' Ragers fight each other. Ours arrive two or three at a time
    after combat, so they're fodder (Fling, sacrifice outlets) or, with an extra combat after main phase 2
    (World at War's rebound, Relentless Assault), an army. Obeka connects in that combat too, which means
    more upkeeps and more Ragers.
- **Stax that only we escape:**
  - Sands of Time: everyone skips the untap step, and in their upkeep everything tapped untaps while
    everything untapped taps. Tap out in response to the trigger and we untap again, in every extra upkeep.
  - Mist of Stagnation: untap one permanent per card in our graveyard each upkeep. It's tagged mass land
    denial, so it's Bracket 4 only.
- **The flip side:** opponents' symmetric punishers (Smokestack, The Abyss, Braids, Cabal Minion, Sulfuric
  Vortex) hit *only us* in each extra upkeep. Removing them before a long turn is mandatory, and the pilot
  needs to know it.
- **The structural fix for that worry: Paradox Haze on ourselves.** It adds a second upkeep to every turn
  of ours, without combat. Every R card then runs at least 2:1 in our favour per round before Obeka connects
  at all.
- **Worry:** the boons feed opponents every round, and some (Wild Evocation, Gate) feed them more than they
  feed us on turns Obeka doesn't connect. The family wins only if she connects often. It's the most
  political family here and the hardest to pilot.

### S. Storm in the extra upkeeps
- **Idea:** every spell cast in an extra upkeep counts toward this turn's storm count before main phase 2.
  The free casts count, and so do the cheap instants cast in each upkeep:
  - rebound;
  - Galvanoth and Panoptic Mirror;
  - Wild Evocation;
  - suspend coming off;
  - Taigam's suspended copies.
- **Payoffs:**
  - Grapeshot, Tendrils of Agony, Brain Freeze, Empty the Warrens.
  - Volcanic Torrent: cascade, then damage to each opposing creature equal to the spell count. It's a
    *one-sided, scaling* sweeper: the Edgar and Giada answer the decks are missing.
  - Aetherflux Reservoir.
  - Surge of Brilliance: draws one per spell cast from *anywhere other than hand*, which describes every free
    Obeka cast.
  - Lock and Load, Storm of Memories, Thunder Salvo.
- **"Second spell each turn" engines** get a second spell for free:
  - Taigam, Master Opportunist (14%);
  - Storm of Saruman and Tomb of Horrors Adventurer (both copy it);
  - Hearthborn Battler, Kraum, Violent Cacophony, Jori En.
- **Honest scale:** a realistic Obeka turn reaches a storm count of 5–7. That's a sweeper, a big draw or a
  15-point drain, not a kill on its own. It's a finishing layer for family E rather than a deck.

### T. Attack triggers that suspend, so the payoff lands the same turn
- **Core:** "whenever you attack" effects that exile something with N time counters:
  - Doom's Time Platform (16%) recurs a graveyard card with two counters;
  - The Tenth Doctor (10%) and Kang Prime (7%) exile from the top of the library;
  - Taigam suspends with four counters.
  If Obeka connects for N or more, it's cast free that same turn.
- **Honest framing (the rebound lesson):** Obeka only makes these faster. The value is the card itself:
  - The Tenth Doctor and Kang Prime are a free card per attack.
  - Doom's Time Platform is a recursion per attack.
  Speed matters here because the free spell lands before main phase 2, while we still have mana and a
  sorcery window.
- **Two oddballs:**
  - Greater Gargadon is a free sacrifice outlet *from exile* (family J).
  - Living End, suspended before combat, resolves in an extra upkeep as a timed mass reanimation and sweeper.

### U. Batteries charged per upkeep, cashed at instant speed
- **Core:**
  - Lotus Blossom: one petal per upkeep, sacrifice for X mana of one colour in main phase 2. A 4-upkeep turn
    is a ritual.
  - Time Bomb: one counter per upkeep; sacrifice to deal that much to each creature *and* each player. A
    symmetric scaling sweeper and a slug at once.
  - Midnight Clock (27%): a 12-counter wheel that Obeka reaches in two or three turns.
  - Aether Vial, Infinite Hourglass, Sun Droplet.
  - The Long Morning's Legacy's Allure, Vile Requiem and Torch Song.
- **Uses Obeka:** threshold value (kind 4). Each hit is a jump in the charge, and the decision about *when*
  to cash in reads the table.
- **Worry:** batteries are slow alone. This is a layer, already half-present in the Long Morning.

### F, revisited: the Zombie count
- **It's a deck, not just a package:** at least 400 Zombie cards and 111 non-Zombie Zombie-makers are legal in
  Grixis.
- **The upkeep core:** Endless Ranks of the Dead (compounds), The Scarab God (drains each opponent per
  Zombie), Graveborn Muse (draws per Zombie), Dreadhorde Invasion (amass 1 per upkeep; 6%), and Archdemon of
  Unx (turns a non-Zombie into a Zombie each upkeep).
- **The ordering is the combo.** With four Zombies and an Obeka hit for 3, put Endless Ranks on the stack
  above The Scarab God in each upkeep. The Ranks make 2, 3, then 4 more (6, 9, 13 Zombies), and the Scarab
  God drains each opponent 6 + 9 + 13 = 28.
- **Worry:** Graveborn Muse at that count draws us to death, so it belongs in the deck only with a way to
  turn it off.

### Upkeep finds that fit several families
- **Feast on the Fallen** (3 mana, 6%): a +1/+1 counter on a creature of ours in *each* upkeep, if an
  opponent lost life last turn. In a four-player game it's nearly always on. It's the cheapest compounding
  piece after the Rings: Obeka grows on everyone's turns, and her own extra upkeeps grow her further.
- **Darkstar Augur with offspring:** two Dark Confidant triggers per upkeep for 4 mana.
- **Magmatic Force:** 3 damage to any target in *each* upkeep. It costs 8, but a 4-player round already
  gives it four shots, and the Obeka turn adds more.
- **Undercity arithmetic (family K):** a dungeon completes in five ventures. Taking the initiative (1), the
  natural upkeep (1) and a 3-damage hit (3) clear it in one turn: Forge, Trap or Stash, Archives, then the
  Throne. With two hits the Forge has made her 4 power, and the next run starts in the same turn.

## Cross-pollination worth exploring
- **K (Undercity) + the Rings:** both grow Obeka per upkeep, so they stack into faster compounding.
  Dungeon Delver doubles the Forge.
- **L (the Ring) as evasion** for any family that needs Obeka to connect.
- **O (Midnight Banshee) as the sweeper layer** for black-heavy builds: B, F, N, Q.
- **D + Treasure:** Tempting Contract and Generous Plunderer make D's main phase 2 real.
- **A + Treasure:** Revel in Riches plus Tempting Contract, with the upkeep check.
- **F + G:** Followed Footsteps on The Scarab God is a drain that doubles twice over.
- **I + J:** Dawn of the Dead plus forced-sacrifice creatures. The upkeep sacrifice puts the creature back
  where the next upkeep can return it.
- **Trigger doublers + any family:** a cheap way to double everything when she connects.
- **R + E (Rite of the Raging Storm + World at War):** the Ragers made in the extra upkeeps attack in the
  rebound's extra combat. Obeka connects again, and the loop runs until the extra combats run out.
- **M + R (Ghirapur Orrery):** the Orrery is a symmetric card whose upkeep clause belongs to us on an Obeka
  turn. Madness gives us a way to empty the hand between upkeeps.
- **S + O:** Volcanic Torrent is a scaling, one-sided sweeper that, unlike Midnight Banshee, doesn't care what
  colour our creatures are.
- **U + B:** Time Bomb is a slug finisher that also wipes the board.
- **F + Feast on the Fallen:** a counter per upkeep on the biggest Zombie Army (Dreadhorde Invasion) reaches
  6 power, and the Invasion's lifelink clause, quickly.

## Questions the tools can answer next
- **Per family, without games:** the engine goldfish ("core engine online by T6") and a per-upkeep value
  model: cards per upkeep, damage per upkeep, whether it compounds.
- **Per family, with games:** the upkeep tally after a few piloted games shows what actually earned.
- **For the trigger doublers:** how often do Roaming Throne or Wizard's Staff plus a Ring show up by T6?
- **For family R:** a symmetric-card ledger. Count how many of these boons' triggers we took versus each
  opponent across piloted games. If Obeka doesn't connect often enough, the boons are a gift to the table.
- **For family S:** the realistic storm count on an Obeka turn, from the same logs: spells cast between
  combat and main phase 2.
