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
- **"Each upkeep" / "each player's upkeep" effects hit us in every extra upkeep.** Opponent-upkeep effects
  aren't multiplied at all.
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
- **Worry:** madness density in UBR is thin; check the pool.

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

## Questions the tools can answer next
- **Per family, without games:** the engine goldfish ("core engine online by T6") and a per-upkeep value
  model: cards per upkeep, damage per upkeep, whether it compounds.
- **Per family, with games:** the upkeep tally after a few piloted games shows what actually earned.
- **For the trigger doublers:** how often do Roaming Throne or Wizard's Staff plus a Ring show up by T6?
