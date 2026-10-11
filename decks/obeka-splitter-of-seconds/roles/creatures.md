# Role: creatures from upkeeps (Obeka, Splitter of Seconds, B3)

Scouted 2026-10-11. Sources: `./edh pool` slices (upkeep+token: 77 cards; upkeep+"to the battlefield": 51;
upkeep+gain control: 22; "activate only during your upkeep": 36; vanishing/fading creatures: 50), two
`jev grep` passes, EDHREC (17,881 Obeka decks). Every pick's oracle text checked with `./edh card`.

**Timing reminders.** Bodies made in Obeka's extra upkeeps arrive after combat, so they can't attack that
turn, but they are untapped blockers for every opponent's turn. Our *normal* upkeep is before combat, so a
steal or reanimation there can attack. "Each opponent's upkeep" effects are not multiplied, but they make
blockers right before that opponent's attack, which is exactly when we need them.

**Scoring.** V = value per upkeep (1–5). D = defence vs go-wide (1–5): blocks fliers, deathtouch, survives a
trade, still there on opponents' turns. Rank = V×D. ★ = top pick. Incl. = Obeka EDHREC inclusion.

## 1. Token makers per upkeep (pool: ~20 real makers in the 77-card slice)

| Card | MV | Incl. | One upkeep yields | Cost per upkeep | Defence | Other role | V×D |
|---|---|---|---|---|---|---|---|
| ★ Dragonmaster Outcast | 1 | 78% | 5/5 flying Dragon (needs 6 lands) | none | 5: flier, big, persistent | wincon | 5×5 |
| ★ Skyline Despot | 7 | 51% | 5/5 flying Dragon while monarch | none | 5; body is a 5/5 flier too | draw (monarch) | 5×5 |
| ★ Thrumming Hivepool | 6 | -- | two 1/1 Slivers with double strike + haste | none | 4: two bodies; first-strike damage kills x/1–x/2 tokens before they hit back. Ground only | wincon w/ Mechanized Production | 4×4 |
| ★ Shrine of Loyal Legions | 2 | -- | +1 charge counter | none ({3},T,sac to cash in) | 4: crack at instant speed in an opponent's combat for X 1/1 Myr: ambush blockers | -- | 3×4 |
| ★ Bonehoard Dracosaur | 5 | 34% | 2 cards playable this turn + 3/1 Dinosaur (land) and/or Treasure | none | 4: the body is a 5/5 flying first striker; the 3/1s are trade-bait | draw, mana | 4×3 |
| Court of Embereth | 4 | 69% | 3/1 Knight; while monarch, X dmg to each opp (X = our creatures) | none | 3: 3/1 trades with any token, ground only | wincon | 4×3 |
| Bitterbloom Bearer | 2 | -- | 1/1 flying Faerie | 1 life | 3: flying chump; the Bearer itself has flash | -- (a creature, so Endless Evil/Footsteps copies compound) | 3×3 |
| Bitterblossom | 2 | 9% | 1/1 flying Faerie Rogue | 1 life | 3: flying chump | -- | 3×3 |
| Thopter Spy Network | 4 | 35% | 1/1 flying Thopter (if we control an artifact) | none | 3: flying chump | draw (artifact creature hits) | 3×3 |
| Ophiomancer | 3 | -- | 1/1 deathtouch Snake, *each* upkeep incl. opponents', only if we control no Snakes | none | 5: deathtouch, refills before every opponent's combat | sac fodder | 1×5 |
| Thieving Amalgam | 7 | -- | each **opponent's** upkeep: manifest their top card (2/2) | none | 4: a fresh 2/2 before each attacker's combat; drains 2 when they die | drain | 2×4 (not multiplied) |
| Abhorrent Oculus | 3 | -- | each **opponent's** upkeep: manifest dread (2/2) | exile 6 from GY to cast | 4: same timing; body is a 5/5 flier | selection | 2×4 (not multiplied) |
| Archdemon of Unx | 7 | -- | sac a non-Zombie, make a 2/2 Zombie (mandatory; eats itself if it's the only non-Zombie) | a creature | 2: net zero bodies | feeds Endless Ranks | 1×2 |
| Goblin Assault | 3 | 5% | 1/1 haste Goblin | none | 2: Goblins must attack each combat, so last turn's tokens are tapped on defence | -- | 2×2 |

## 2. Compounding makers (pool: 11)

| Card | MV | Incl. | One upkeep yields | Cost | Defence | Other role | V×D |
|---|---|---|---|---|---|---|---|
| ★ Extravagant Replication | 6 | 65% | copy of any nonland permanent: on Dragonmaster Outcast / Bitterblossom / Hivepool / Court of Embereth growth goes quadratic | none | as good as the target (Outcast copies: 5) | copies removal/draw engines too | 5×4 |
| ★ Mechanized Production | 4 | 62% | copy of the enchanted artifact. On **Thopter Assembly**: a 5/5 flier per upkeep (order the Production trigger to resolve first, so Assembly's "no other Thopters" check fails and it never bounces). On **Thrumming Hivepool**: k Hivepools make 2k Slivers. Eight copies = win | none | 5 (Assembly) / 4 (Hivepool) | alt-win | 5×5 |
| ★ Endless Evil | 3 | 9% | 1/1 copy of our enchanted creature. Dragonmaster Outcast is already 1/1, so it's a perfect copy: quadratic 5/5 Dragons. On Bonehoard Dracosaur: a 1/1 flying first-strike Dracosaur that digs 2 more cards each upkeep | none | 4–5 | draw (on Dracosaur/Strix) | 4×4 |
| ★ Chronozoa | 4 | 14% | removes a time counter from every Chronozoa; each one that runs out becomes two copies (3/3 fliers that also have vanishing 3) | none | 4: 3/3 fliers. Killed with counters left = no copies | -- | 4×4 |
| Followed Footsteps | 5 | 9% | full copy of the enchanted creature, **any** controller's (copy their best blocker) | none | as target | -- | 4×4 |
| Mirrorhall Mimic // Ghastly Mimicry | 4 / disturb 5 | -- | clone first; disturbed it's a Footsteps that enchants any creature | none | as target | clone | 4×3 |
| Court of Vantress | 4 | 67% | copy of an artifact/enchantment while monarch (Bitterblossom, Shrine, Hivepool; a Court of Embereth copy re-crowns us) | none | indirect | draw (monarch) | 3×3 |
| Flesh Duplicate | 2 | -- | clone with vanishing 3: copying Dragonmaster Outcast = three Dragons before it dies; copying Chronozoa = a second line | none | indirect | -- | 3×3 |
| Dreadhorde Invasion | 2 | 6% | +1/+1 on one Zombie Army | 1 life | 3: one big ground blocker, not width; lifelink at 6+ only when attacking | -- | 2×3 |
| Endless Ranks of the Dead | 4 | -- | X 2/2 Zombies, X = half our Zombies. Needs 2 Zombies first, and this pool has almost none (Army, Archdemon, Sarcomancy) | none | 3 | -- | 0–3×3 |

## 3. Reanimation onto the battlefield at upkeep (pool: ~15 real reanimators in the 51-card slice)

| Card | MV | Incl. | One upkeep yields | Cost | Defence | Other role | V×D |
|---|---|---|---|---|---|---|---|
| ★ Virtue of Persistence | 7 (adv. 2) | 18% | creature from **any** graveyard, permanently ours | none | 5: the best blocker in four graveyards | removal (Locthwain Scorn −3/−3) | 5×5 |
| ★ Portal to Phyrexia | 9 | 11% | creature from any graveyard | none | 5: the ETB makes each opponent sacrifice 3 creatures, which blunts go-wide | removal | 5×5 |
| ★ Sheoldred, Whispering One | 7 | 20% | creature from our graveyard | none | 5: 6/6 body; edict on each opponent's upkeep (not multiplied) | removal | 4×5 |
| ★ Curse of Unbinding | 7 | -- | on **ourselves**: each of our upkeeps, reveal until a creature and put it onto the battlefield, mill the rest (feeds Virtue). On an opponent: steal one creature per round from their library (not multiplied) | self-mill | 4: permanent bodies | self-mill/theft | 4×4 |
| ★ Chaos Shrine's Black Crystal | 4 | -- | one of our dead nontoken creatures back (finality counter) | none | 3: only what died while it was out | -- | 3×3 |
| The Soul Stone | 2 (+7 harness) | 7% | creature from our graveyard | one-time {6}{B} + exile a creature | 4 | mana rock | 3×4 |
| Gisa, Glorious Resurrector | 4 | -- | every opposing creature that died since our last upkeep, ours with decayed | none | 1: decayed can't block | sac fodder, anti-recursion | 4×1 |
| Braids, Conjurer Adept | 4 | 36% | an artifact/creature/land from hand (symmetric) | none | 2: helps every opponent too | ramp | 3×2 |

## 4. Self-returning creatures (pool: ~12)

| Card | MV | Incl. | One upkeep yields | Cost | Defence | Other role | V×D |
|---|---|---|---|---|---|---|---|
| ★ Rekindling Phoenix | 4 | -- | if dead: back in our next upkeep (extra upkeeps count) | none | 4: 4/3 flier blocks each round; gone for the rest of that round if it dies on defence | -- | 3×4 |
| ★ Kuldotha Phoenix | 5 | -- | {4}: back from graveyard, repeatable each upkeep (needs 3 artifacts) | {4} | 4: 4/4 flier | -- | 3×4 |
| Necrosavant | 6 | -- | {3}{B}{B} + sac a creature (Snake, Faerie): back as a 5/5 | 5 mana + a body | 4 | -- | 2×4 |
| Nether Spirit | 3 | -- | back if it's the only creature card in our graveyard | none | 2: 2/2, unreliable | -- | 2×2 |
| Ashen Ghoul / Nether Shadow | 4 / 2 | -- | back if 3+ creature cards are above it in our graveyard | {B} / none | 1: graveyard order rarely cooperates | -- | 1×1 |

## 5. Stealing at upkeep (pool: ~10 real ones; 22-card slice plus exchange effects)

Steals made in our normal upkeep can attack (it's before combat). Steals made in extra upkeeps are post-combat:
use them for ETB/tap abilities, sacrifice them before end of turn, or keep them only if the steal is permanent.

| Card | MV | Incl. | One upkeep yields | Cost | Defence | Other role | V×D |
|---|---|---|---|---|---|---|---|
| ★ Legacy's Allure | 2 | -- | +1 treasure counter; sacrifice **at instant speed** for a permanent steal of a creature with power ≤ counters | none | 5: steal an attacker in their combat, and it blocks for us after | removal | 3×5 |
| ★ Puca's Mischief | 4 | -- | permanent exchange: our nonland permanent for theirs of equal or lower MV (needs fodder to give each time) | a permanent | 4: what we take stays | removal | 3×4 |
| ★ Dominus of Fealty | 5 | 9% | any permanent until end of turn, untapped with haste | none | 3: the 4/4 flier blocks; steals are gone by their turn unless we sacrifice them | removal w/ sac outlet | 4×3 |
| Inevitable Betrayal | 0 (suspend {1}{U}{U}) | 25% | ticks down 1; on the last counter, their best library creature is ours permanently | none | 4: arrives post-combat, stays | tutor-steal | 2×4 |
| Frenzied Fugue | 4 | -- | the same enchanted permanent again (extra upkeeps only re-untap it) | none | 1: theirs again on their turn | removal w/ sac outlet | 1×1 |

## Notable rejects

- **Infernal Genesis**: symmetric, so it hands go-wide opponents a token stream on their own upkeeps.
- **Rite of the Raging Storm**: our Lightning Ragers are sacrificed at that turn's end step, so they never block.
- **Tombstone Stairwell**: symmetric, cumulative upkeep multiplied by Obeka, tokens die every end step.
- **Ichorid**: sacrificed at every end step, so it's never there on defence.
- **Hell's Caretaker**: the {T} cost means once per turn no matter how many upkeeps.
- **Gisa** as a defensive card: decayed bodies can't block. Fine as fodder, not as a wall.
- **Infernal Denizen / Coffin Puppets / Akuta**: sacrifice lands per upkeep or per return. Obeka multiplies the bill.
- **Eternal Dominion**: a permanent steal every upkeep, but epic stops us casting spells for the rest of the game, Obeka included.
- **Alexios / Emberwilde Djinn**: change hands on opponents' upkeeps, so they're theirs exactly when we need a blocker.
- **Tetravus / Thopter Assembly alone**: fixed counters, or a one-shot that re-buys itself. Only good under Mechanized Production.
- **Dawn of the Dead / Rescue from the Underworld / rebound token spells (Ojutai's Summons)**: temporary, or one-shot per card.
