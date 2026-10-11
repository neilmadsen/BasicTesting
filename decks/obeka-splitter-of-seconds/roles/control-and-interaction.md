# Obeka role scout: control on upkeep (C) and interaction that rides the upkeep (D)

Bracket 3. "N upk" means the number of upkeeps the card needs; on a turn Obeka connects for N, it all happens before main phase 2.
EDHREC = share of all 17,881 Obeka decks ("--" = not on the page, roughly under 4%). Deck: TT = Twice-Told, LM = Long Morning.
Go-wide: Y / P(artly) / N. A/E: does it answer artifacts or enchantments. Every card below was read in full with `./edh card` or the pool dump (same oracle DB).

## How the pool was searched

| Slice | Size | Read |
|---|---|---|
| Nonland cards with "beginning of your/each/each player's upkeep" | 734 (99 on Obeka's EDHREC page) | all: 258 control-relevant in full, plus the 197 of the rest that touch removal or counters |
| Jev rank, narrow control brief, whole nonland pool | 17,751 | top 300 |
| Jev greps: alpha-strike instants / delayed removal / upkeep recursion / upkeep-only activations / hand control / tutors / politics | 2,203 / 17,751 x6 | top 60 / 6 / 39 / 2 / 50 / 4 / 13 |
| Rebound / suspend with an interactive effect / "next upkeep" removal | 21 / 48 / 10 | all |
| Instant counterspells MV<=3 | 206 (7 on Obeka's page) | the best 15 |

Finalists: 96 cards. Graveyard hate, goad, and tutoring an answer on upkeep are almost empty slices in UBR (see C4 and C5).

---

## Role C: control on upkeep

### C1. Spot (one target per upkeep)

| # | Card | MV | EDHREC | Each upkeep | Go-wide | A/E | Cost per upkeep | Self-harm | Other roles | Deck |
|---|---|---|---|---|---|---|---|---|---|---|
| **1 TOP** | Court of Ire | 5 | 77% | 2 damage to any target, 7 as monarch | P (one body) | N | 0 | none | monarch draw, wincon | TT LM |
| **2 TOP** | Argentum Masticore | 5 | -- | Discard a card: destroy an opponent's nonland permanent with MV <= the discarded card's MV | P | **Y** (any nonland) | one discard (or sac it) | card loss multiplies | 5/5 first strike, pro-multicolored | gem |
| **3 TOP** | Torch Song | 3 | -- | +1 verse; {2}{R}, sac: X to any target, instant speed | P | N | 0 | none | burn finisher | LM |
| **4 TOP** | Weed-Pruner Poplar | 5 | -- | target creature -1/-1 until EOT. **Stacks within the turn**: 4 upkeeps make it -4/-4 on one creature, or kill four X/1s | P (X/1 tokens) | N | 0 | mandatory target (Obeka can take it) | 3/3 body | gem |
| **5 TOP** | Bomb Squad | 4 | -- | +1 fuse on each fused creature. At 4: destroy + 4 damage to its controller. Tap pre-combat, connect for 3 = dead | N | N | 0 | none | burn | gem |
| 6 | Shrine of Burning Rage | 2 | -- | +1 charge (and per red spell); {3},T,sac: that much to any target | N | N | 0 | none | finisher | gem |
| 7 | Fatal Attraction | 3 | -- | 2 on ETB, then 4 per upkeep to the enchanted creature | N | N | 0 | none | -- | LM |
| 8 | Glistening Oil | 2 | -- | -1/-1 counter on the enchanted creature; returns to hand when it dies, so recast it | N | N | 0 | **the creature gains infect** until it dies | feeds Crumbling Ashes | gem |
| 9 | Magmatic Force | 8 | 11% | 3 to any target in **every** upkeep (all turns) | P | N | 0 | none | 7/7 | -- |
| 10 | Tidal Force | 8 | -- | tap/untap target permanent in every upkeep. Tap an opponent's best attacker in their upkeep | P | Y (tap rocks) | 0 | none | untap our stuff | -- |
| 11 | Raka Sanctuary | 3 | -- | 1 to target creature (Obeka is the blue permanent) | P | N | 0 | none | -- | weak |
| 12 | Honden of Infinite Rage | 3 | -- | 1 to any target (2+ only with other Shrines) | P | N | 0 | legendary | -- | weak |

### C2. Scaling or mass

| # | Card | MV | EDHREC | Each upkeep | Go-wide | A/E | Cost | Self-harm | Other | Deck |
|---|---|---|---|---|---|---|---|---|---|---|
| **1 TOP** | Recantation | 5 | -- | +1 verse; {U}, sac: return up to X **permanents** to hand, **instant**. Tokens cease to exist | **Y** | **Y** | 0 | none | saves our stuff, Pact exit | LM |
| **2 TOP** | Midnight Banshee | 6 | -- | -1/-1 counter on each **nonblack** creature. Obeka is black, so she's safe. Also removes +1/+1 counters | **Y**, but misses black armies (Edgar's Vampire tokens are black) | N | 0 | hits our nonblack creatures | 5/5 wither | gem |
| **3 TOP** | Vile Requiem | 4 | -- | +1 verse; {1}{B}, sac: destroy up to X nonblack creatures, **instant** | **Y** (not black) | N | 0 | none | -- | LM |
| **4 TOP** | Time Bomb | 4 | -- | +1 time counter; {1},T,sac: that much to each creature and player, **instant** | **Y** | N | 0 | **symmetric**. Obeka (2/5) survives up to 4 | alpha-strike answer | gem |
| **5 TOP** | Sphere of Annihilation | X+1 | -- | One-shot at our next upkeep (same turn on a connect): exile all creatures and planeswalkers with MV <= X, and the same cards in graveyards. **X=0 for {B} exiles every token**; X=3 spares Obeka | **Y** | N | 0 | our creatures with MV <= X too | graveyard hate | gem |
| 6 | Festering March | 5 (susp 3 for {2}{B}) | -- | Opponents' creatures -1/-1, then it re-suspends itself with 3 counters. A one-sided sweep every 3 upkeeps, forever | Y (X/1) | N | 0 | none | -- | gem |
| 7 | Powder Keg | 2 | -- | "may" +1 fuse; T,sac: destroy each artifact and creature with exactly that MV. 0 counters = all tokens, Treasures and Clues, instant | Y (tokens) | **Y** (artifacts) | 0 | symmetric at that MV | -- | gem |
| 8 | Festering Evil | 5 | -- | 1 to each creature and player; {B}{B}, sac: 3 to each | Y (X/1) | N | 0 | **we take 1 per upkeep** | -- | -- |
| 9 | Purging Scythe | 5 | -- | 2 to the creature with least toughness (not targeted; we break ties) | P | N | 0 | may hit our tokens | -- | -- |
| 10 | Coercive Portal | 4 | -- | Vote: carnage destroys all nonland permanents, homage draws. Ties draw | Y if voted | Y | 0 | symmetric wipe | draw | see C5 |
| 11 | The Moment | 2 | -- | +1 time counter; {3},T, sorcery speed: destroy each nonland permanent with MV <= counters. Its {2},T phases our creature out until The Moment leaves | Y | **Y** | 0 | symmetric unless phased | -- | gem (slow) |
| 12 | Corrosion | 3 | -- | Rust counter on each artifact of target opponent, destroy those with MV <= rust | N | Y (art.) | **cumulative {1}: 1+2+3+4 = 10 on a 3-hit turn** | -- | -- | niche |
| 13 | Plague Spitter | 3 | -- | 1 to each creature and player. Dies on the 2nd ping of a turn: 3 total | Y (X/3) | N | 0 | symmetric | -- | -- |
| 14 | Crumbling Ashes | 2 | -- | destroy target creature with a -1/-1 counter | P | N | 0 | none | -- | only with Banshee or Oil. **Fails vs +1/+1-counter boards** (counters annihilate) |

### C3. Theft

| # | Card | MV | EDHREC | Each upkeep | Go-wide | A/E | Cost | Self-harm | Deck |
|---|---|---|---|---|---|---|---|---|---|
| **1 TOP** | Dominus of Fealty | 5 | 9% | steal any permanent until EOT, untapped and hasty: a different one per upkeep | N | Y | 0 | none | LM |
| **2 TOP** | Puca's Mischief | 4 | -- | swap one of ours for theirs with equal or lower MV (Myr or Treasure for their engine) | N | **Y** | 0 | gives a card away | LM |
| **3 TOP** | Legacy's Allure | 2 | -- | +1 treasure counter; sac: steal a creature with power <= counters, any time | N | N | 0 | none | LM |
| **4 TOP** | Frenzied Fugue | 4 | -- | re-steal the enchanted permanent and untap it (only on our turns) | N | Y | 0 | none | LM |
| **5 TOP** | Virtue of Persistence | 7 (adv. 2) | 18% | reanimate any graveyard's creature under our control | N | N | 0 | none | LM |
| 6 | Gisa, Glorious Resurrector | 4 | -- | their dead creatures come to us (combat deaths return in the extra upkeeps) | N | N | 0 | none | LM |
| 7 | Enslave / Biting Tether | 6 / 5 | -- | permanent steal; Enslave pings the owner, Tether shrinks it (dies over time) | N | N | 0 | none | LM / -- |
| 8 | Inevitable Betrayal | susp 3 | 25% | best creature from their library, same turn on a 3-hit | N | N | 0 | none | -- |
| 9 | Portal to Phyrexia | 9 | 11% | reanimate from any graveyard; ETB 3-creature edict | P | N | 0 | none | -- |

Rejected here: Binding Grasp, Vapor Snare and Infernal Denizen (their upkeep costs multiply: {1}{U}, a land, or two Swamps per upkeep). Dichotomancy needs tapped permanents, and opponents' permanents are untapped on our turn. Emberwilde Djinn and Alexios hand themselves around.

### C4. Hand and graveyard control

| # | Card | MV | EDHREC | Each upkeep | Cost | Deck |
|---|---|---|---|---|---|---|
| **1 TOP** | Court of Ambition | 4 | 71% | each opponent discards 1 (2 as monarch) or loses 3 (6) | 0 | staple |
| **2 TOP** | Discordant Dirge | 5 | -- | +1 verse; {B}, sac: look at hand, pick X discards, any time | 0 | gem |
| **3 TOP** | Honden of Night's Reach | 4 | -- | target opponent discards 1 (per Shrine) | 0 | gem |
| **4 TOP** | Xanathar, Guild Kingpin | 6 | 9% | target opponent can't cast spells this turn: on a connect, lock a different opponent per extra upkeep through our main phase 2 | 0 | LM |
| **5 TOP** | Sphere of Annihilation | X+1 | -- | the graveyard half of C2 #5 | 0 | gem |
| 6 | Shrine of Limitless Power | 3 | -- | +1 charge (and per black spell); {4},T,sac: target discards that many | 0 | gem |
| 7 | Mindstab | susp 4 for {B} | -- | 3 discards on a 3-hit turn | 0 | -- |
| 8 | Entrails Feaster | 1 | -- | exile a creature card from any graveyard (grows) | 0 | thin |
| 9 | Triumph of Cruelty | 3 | -- | discard, only if we control the creature with the greatest power (Obeka is 2) | 0 | weak |

Tutoring an answer on upkeep: nothing good. Ratcatcher, Blood Speaker and Curse of Misfortunes are tribal. Next best: Profane Tutor (suspend 2, 36%; resolves the same turn on a 2-hit) and Doom's Time Platform (D3).

### C5. Political

| Card | MV | EDHREC | Each upkeep | Note |
|---|---|---|---|---|
| **Coercive Portal TOP** | 4 | -- | vote carnage (destroy all nonland permanents) or homage (draw) | A card per upkeep, and the table knows a wipe is one vote away. On a connect it's 4 votes. Pair with Illusion of Choice |
| **Xanathar TOP** | 6 | 9% | silence one opponent per upkeep | Choose who gets locked |
| **Rite of the Raging Storm** | 5 | -- | each player gets a 5/1 trample haste Rager on their own upkeep that **can't attack us** | Forces opponents to hit each other. Ours arrive after combat (sac fodder) |
| Curse of the Cabal | susp 2 | 8% | sac half their permanents. Opponents can delay it on their upkeeps by sacrificing a permanent; in our extra upkeeps only we act | Taxes the table either way |
| Court of Ire / Ambition | -- | -- | monarch fights | -- |

No UBR card goads on our upkeep. Slicer goads on opponents' upkeeps, so Obeka doesn't help it.

---

## Role D: interaction that rides the upkeep

### D1. Delayed removal made immediate

| # | Card | MV | EDHREC | Upkeeps needed | Effect | Go-wide | A/E | Deck |
|---|---|---|---|---|---|---|---|---|
| **1 TOP** | Reality Acid | 3 | -- | 3 (vanishing 3) | enchanted **permanent** is sacrificed when the Aura leaves. Removing the Aura early still kills it | N | **Y** (anything) | gem |
| **2 TOP** | Parasitic Implant | 4 | -- | 1 | sacrifice the creature (beats indestructible), we get a 1/1 Myr | N | N | gem |
| **3 TOP** | Suspended Sentence | 4 / susp {1}{B} | 46% | 3 | destroy + 3 life loss, then re-suspends itself: repeats every 3 upkeeps | N | N | staple |
| **4 TOP** | Sphere of Annihilation | X+1 | -- | 1 | mass exile at MV <= X (C2) | **Y** | N | gem |
| **5 TOP** | Parallax Dementia | 2 | -- | 2 (fading 1) | destroy (no regeneration). Removing the Aura early also kills the creature. Gives +3/+2 until then | N | N | gem |
| 6 | Mark of Eviction | 1 | -- | 1 | bounce the creature and its Auras (tokens die) | P | N | gem |
| 7 | Reality Strobe | 6 / susp {2}{U} | 19% | 3, recurring | bounce any permanent every 3 upkeeps | P | Y | -- |
| 8 | Festering March | susp {2}{B} | -- | 3, recurring | one-sided -1/-1 | Y | N | gem |
| 9 | Shivan Meteor | susp {1}{R}{R} | -- | 2 | 13 to a creature | N | N | -- |
| 10 | Rift Bolt | susp {R} | -- | 1 | 3 to any target for one mana, same turn | N | N | -- |
| 11 | Phthisis | susp {1}{B} | 7% | 5 | destroy + life loss of power + toughness | N | N | -- |
| 12 | Plunder | susp {1}{R} | -- | 4 | destroy an artifact (or land) | N | Y (art.) | -- |
| 13 | Arc Blade | susp {2}{R} | 8% | 3, recurring | 2 to any target | N | N | -- |
| 14 | Riftwing Cloudskate | susp {1}{U} | -- | 3 | flier, bounce any permanent | N | Y | -- |

### D2. Rebound (the copy fires in the first extra upkeep)

| Card | MV | EDHREC | Effect x2 | Go-wide | A/E | Deck |
|---|---|---|---|---|---|---|
| **Void Squall TOP** | 5 | -- | bounce a nonland permanent, twice | N | **Y** | gem |
| **Consuming Vapors TOP** | 4 | -- | edict + lifegain, twice | N | N | gem |
| Staggershock | 3 | -- | 2 to any target, twice | P | N | TT |
| Fantastic Elasticity | 3 | -- | bounce a nonland permanent, or regrow an instant/sorcery | N | Y | TT |
| Ojutai's Breath | 3 | -- | tap + freeze, twice | N | N | -- |
| Cast Through Time | 7 | -- | rebound for every instant and sorcery | -- | -- | TT |

### D3. Recursion of answers per upkeep

| Card | MV | EDHREC | Each upkeep | Note |
|---|---|---|---|---|
| **Doom's Time Platform TOP** | 4 | 16% | Whenever we attack: a nonland card from our graveyard gains suspend 2. **Connect for 2+ and it's cast free the same turn.** Re-buys Feed the Swarm, Chaos Warp, Void Squall, Toxic Deluge (X<=4) | Useless on counterspells (nothing to counter in an upkeep) |
| **Exalted Flamer of Tzeentch TOP** | 4 | 7% | random instant/sorcery from graveyard to hand; pings each opponent per spell | random |
| Charmbreaker Devils | 6 | -- | same, random; +4/+0 per spell | Flamer is cheaper |
| Wildfire Devils | 4 | 22% | random **player's** graveyard: copy an instant/sorcery and cast it free | random, can backfire |
| Death Spark | 1 | -- | returns for {1} if a creature card is directly above it in the graveyard | fiddly |
| Rekindled Flame / Exile into Darkness | 4 / 5 | -- | return to hand if an opponent is hellbent / if we have the most cards in hand | conditional |

### D4. Cheap counterspells (none scale with upkeeps except Lilting Refrain)

| Card | MV | EDHREC | Note | Deck |
|---|---|---|---|---|
| **Counterspell TOP** | 2 | 56% | hard counter | TT LM |
| **Swan Song TOP** | 1 | 18% | stops removal or wipes aimed at Obeka's engine | TT LM |
| **Fierce Guardianship TOP** | 3 | 20% | free with Obeka out (Game Changer) | TT LM |
| **Mana Drain TOP** | 2 | 17% | mana arrives in our next main phase | LM |
| **Lilting Refrain TOP (gem)** | 2 | -- | +1 verse per upkeep; sac: counter unless they pay X. On a 3-hit turn it's +4 at once, so effectively a hard counter held at 0 mana | -- |
| Drown in the Loch | 2 | -- | counter or kill | TT LM |
| An Offer You Can't Refuse / Arcane Denial | 1 / 2 | 38% / 34% | gives them value | TT |
| Force of Negation / Spell Pierce / Stern Scolding | 3 / 1 / 1 | -- | narrow | -- |
| Pact of Negation (trap) | 0 | -- | **the {3}{U}{U} comes due in the first extra upkeep** if cast on our turn before a connect | reject |

### D5. Instant-speed answers to an alpha strike (UBR)

| Card | MV | EDHREC | Effect | Obeka-safe? | Deck |
|---|---|---|---|---|---|
| **Aetherize TOP** | 4 | -- | all attackers to hand (tokens gone) | yes | TT LM |
| **Aetherspouts TOP** | 5 | -- | attackers to the top or bottom of the library | yes | TT LM |
| **Recantation / Vile Requiem / Time Bomb / Powder Keg** | -- | -- | activated during combat (C2) | yes / yes / <=4 dmg / MV-dependent | LM / LM / gem / gem |
| **Cyclonic Rift TOP** | 2 (7) | 21% | overload, one-sided, at end of turn or in combat | yes | LM (GC) |
| **Sudden Spoiling** | 3 | -- | split second: one player's creatures become 0/2 with no abilities | yes | gem |
| Cower in Fear / Make Obsolete | 3 | -- | opponents' creatures -1/-1 | yes | gem |
| Fiery Cannonade / Kozilek's Return | 3 | -- | 2 to each creature | yes (5 toughness) | -- |
| Electrickery (overload) | 2 | -- | 1 to each creature we don't control | yes | -- |
| Rakdos Charm | 2 | 10% | each creature deals 1 to its controller (20 tokens = 20 damage); also artifact or graveyard mode | yes | -- |
| Cryptic Command | 4 | -- | tap all opponents' creatures (cast in their beginning of combat) + counter/draw | yes | -- |
| Evacuation | 5 | -- | all creatures to hand | Obeka bounces too | TT |
| Darkness | 1 | -- | prevent all combat damage | yes | -- |
| Delayed Blast Fireball | 3 | -- | 2 to each opponent's creature (5 from exile) | yes | TT |

Not instants, but important: **Witch's Vengeance** (sorcery, -3/-3 to one creature type) is the clean answer to Edgar Vampires and Giada Angels. Banshee and Requiem miss black Vampires.

---

## Notable rejects

- **Harbinger of Night**: symmetric -1/-1 counters cancel Obeka's Ring +1/+1 counters and shrink her for good.
- **Braids, Cabal Minion; The Abyss; Magus of the Abyss; Kuon's Essence; Woebringer Demon; Smokestack; Necrogen Mists; Bottomless Pit; Tangle Wire**: "each player's upkeep, that player..." hits only us in the extra upkeeps.
- **Traveling Plague**: the opponent re-attaches it when the creature leaves, so it ends up on Obeka and grows in every upkeep.
- **Culling Scales**: lowest MV among all permanents is our Treasure or Sol Ring.
- **Gate to Phyrexia**: "only once each turn", so it doesn't scale.
- **Wave of Terror**: triggers in the draw step, so no scaling. **Magmatic Core**: cumulative upkeep cost explodes.
- **Lavabrink Floodgates**: we control its doom counters in our extra upkeeps, but its 6 damage to each creature kills Obeka.
- **Strangling Grasp**: the victim chooses, so a go-wide player sacrifices a token, or the enchanted creature, which ends it.
- **Pact of Negation, Slaughter Pact**: the payment lands in our first extra upkeep.
- **Season of the Witch**: 2 life per upkeep, multiplied.
- **Capricious Efreet, Pyroclast Consul**: random.
