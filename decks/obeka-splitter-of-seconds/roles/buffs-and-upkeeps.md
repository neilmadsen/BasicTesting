# Obeka roles: "connect for more" and "more upkeeps"

Scouted 2026-10-11. Oracle text checked with `./edh card` / `./edh pool`. EDHREC % = share of Obeka's
17,881 decks ("--" = not on her page). **Bold** = top pick. Other-role tags: D draw, C creature,
X control/interaction, M mana, P protection, E evasion.

## Timing rules that sort these lists

- Obeka's upkeeps arrive **after combat**. Paradox Haze's and The Ninth Doctor's extra upkeeps arrive
  **before combat**, so Ring counters gained in them *do* help this turn's attack.
- Double strike makes Obeka's trigger fire twice (first-strike and regular damage): 2x upkeeps.
- An extra combat that comes after her upkeeps lets this turn's growth hit again. Rule 500.8 says the most
  recently created extra step or phase happens first. Her trigger (combat damage) is created after Karlach's
  or Genji Glove's combat (declare attackers), so her upkeeps come first and the second swing is bigger.
- Shroud (Greaves, Whispersilk) also blocks our own Psychotic Fury, Krydle, Rogue's Passage and equips. Hexproof doesn't.
- Fixed power caps (Access Tunnel, Thieves' Tools, Escape Tunnel) fight the growth plan.

---

## Role 1: Make Obeka connect, and connect for more

### 1a. Compounding counters (pool depth: ~9 that target her, so thin)
| # | Card | MV | Type | EDHREC | What it does for her | Cost / weakness | Also |
|---|---|---|---|---|---|---|---|
| 1 | **Ring of Valkas** | 2 | Equipment | 71% | +1/+1 counter per upkeep (she's red); haste | Each Ring is only +1/upkeep | haste |
| 2 | **Ring of Evos Isle** | 2 | Equipment | 67% | +1/+1 per upkeep (blue); {2}: hexproof | — | P |
| 3 | **Ring of Xathrid** | 2 | Equipment | 61% | +1/+1 per upkeep (black); {2}: regenerate | — | P |
| 4 | **Feast on the Fallen** | 3 | Enchantment | 6% | *Each* upkeep: +1/+1 counter if an opponent lost life last turn. Reliable on all 3 opponents' upkeeps after she hits; in our extra upkeeps only if someone lost life on the previous turn | Conditional on our own upkeeps | — |
| 5 | Agent of the Shadow Thieves | 2 | Background (works from the 99) | -- | Attacking the life leader: +1/+1 counter, deathtouch, **indestructible** | Must attack highest-life player | P |
| 6 | Security Bypass | 2 | Aura | 11% | Unblockable attacking alone; connive on hit (+1/+1 counter if nonland discarded) | Aura 2-for-1 risk | E, D |
| 7 | Drillworks Mole | 1 | Art. creature | -- | {2},T: counter on her (and itself) each turn | Slow | C |
| 8 | Sword of Truth and Justice | 3 | Equipment | -- | +2/+2, pro W/U; hit = counter + proliferate | Proliferate adds only +1 to her | P |
| 9 | Astarion's Thirst | 4 | Instant | -- | Exile a creature, put its power in counters on her | — | X |

### 1b. Big static power (172 equipment/aura buffs in pool; ~10 worth it)
| # | Card | MV | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|
| 1 | **Wrecking Ball Arm** | 2 | -- | Base 7/7 (counters still stack on top); can't be blocked by power ≤2; equip legendary {3} | Legendary | E |
| 2 | **Conqueror's Flail** | 2 | 6% | +3/+3 (3 colours); **opponents can't cast spells during your turn**, so no instant-speed removal or fog in combat | Equip {2} | P, X |
| 3 | **Commander's Plate** | 1 | -- | +3/+3, pro white + green; equip commander {3} | — | P |
| 4 | Dragonfire Blade | 1 | 12% | +2/+2, hexproof from monocolored; equip {1} on her | Multicolor removal still hits | P |
| 5 | Civic Saber | 1 | -- | +3/+0 for 1, equip {1} | No protection | — |
| 6 | Champion's Helm | 3 | 12% | +2/+2, hexproof while legendary; equip {1} | — | P |
| 7 | Bloodsworn Steward | 4 | -- | Commander +2/+2 and haste; 4/4 flier | Creature, dies to removal | C, haste |
| 8 | Unstable Molecule Suit | 3 | -- | +2/+2, indestructible; equip commander {2} | — | P |
| 9 | Blackblade Reforged | 2 | 20% | +1/+1 per land; equip legendary {3} | — | — |
| 10 | Hero's Heirloom | 2 | -- | +2/+1, trample + haste on legendary | — | haste |

### 1c. Double strike (doubles her trigger *and* the damage). ~12 playable of ~40
| # | Card | MV | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|
| 1 | **Hard-Won Jitte** | 2 | -- | Plain double strike, equip {2}. A cheaper Fireshrieker | — | — |
| 2 | **Psychotic Fury** | 2 | -- | Instant: DS on a multicolored creature (her) + draw | One-shot | D |
| 3 | **Blacksmith's Talent** | 1 | -- | L2 auto-equips each combat; L3: equipped creatures have DS + haste on your turn | {R}+{2}{R}+{3}{R} total | haste |
| 4 | Lizard Blades | 2 | 37% | DS, reconfigure {2}; 1/1 DS body otherwise | — | C |
| 5 | Fireshrieker | 3 | 10% | DS, equip {2} | Worse Jitte | — |
| 6 | War Machine, Avenging Arsenal | 5 | -- | On attack, attacking *modified* creatures gain DS (Rings/counters count) | Must attack too | C |
| 7 | Embercleave | 6 | 7% | Flash, DS + trample, cost reduction | Pricey alone | — |
| 8 | Blood Mist | 4 | -- | Each combat: target creature gains DS | Enchantment does nothing else | — |
| 9 | Genji Glove | 5 | 9% | DS + untap + extra combat | Equip {3} | extra combat |
| 10 | The Spear of Leonidas | 3 | -- | On attack: DS, or a 3/2 token, or rummage | Legendary | D |
| — | Temur Battle Rage (6%), Raphael the Nightwatcher, Leyline Axe (10%), Savage Beating | | | backups | | |

### 1d. Evasion (~25 playable among ~110 matches)
| # | Card | MV | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|
| 1 | **Brotherhood Regalia** | 2 | 37% | Unblockable + ward {2}; equip legendary {1} | — | P |
| 2 | **Silent Arbiter** | 4 | 41% | Max one blocker, and she has menace, so she can't be blocked; also caps attacks on us | Symmetric | X, C |
| 3 | **Key to the City** | 2 | -- | T, discard: unblockable; untaps → pay {2} draw | Costs a card | D |
| 4 | **Krydle of Baldur's Gate** | 2 | -- | Whenever you attack, {2}: target creature unblockable | Body is small | C |
| 5 | **Psychic Paper** | 2 | -- | Unblockable + ward {1}, equip {2}. Replaces her name/type: name **Warlock** to keep Roaming Throne working, or **Wizard** to enable Wizard's Staff equip {1} / Harmonic Prodigy | Type swap | P |
| 6 | Whispersilk Cloak | 3 | 46% | Unblockable + shroud | Shroud blocks own tricks | P |
| 7 | My Precious | 3 | 6% | Hexproof + unblockable; equip {2}+2 life; adventure draws 2 | Life | P, D |
| 8 | Crypsis | 2 | -- | Instant after attacks: pro creatures you don't control (= unblockable) + untap | One-shot | P |
| 9 | Veil of Secrecy | 2 | -- | Instant: shroud + unblockable | One-shot | P |
| 10 | Kaito, Cunning Infiltrator | 3 | -- | +1: unblockable + loot; grows when she connects | PW | D |
| 11 | Rogue's Passage / Shizo / The Black Gate | land | 68/25/14% | Land-slot evasion | Mana-hungry | — |
| — | Aqueous Form (64%), Aether Tunnel (36%), Thassa (49%), Sword Coast Sailor (16%), Trailblazer's Boots (28%), Bria, Cosmotronic Wave, Untimely Malfunction (10%) | | | solid backups | | |

### 1e. Protection (~20 playable)
| # | Card | MV | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|
| 1 | **Swiftfoot Boots** | 2 | 68% | Hexproof + haste, equip {1} | Wipes | haste |
| 2 | **Deflecting Swat** | 0* | 20% | Free redirect of removal | — | X |
| 3 | **Conqueror's Flail** | 2 | 6% | (see 1b) shuts off instants on our turn | — | X |
| 4 | Lightning Greaves | 2 | 44% | Shroud + haste, equip 0 | Shroud blocks own targeting | haste |
| 5 | Mithril Coat | 3 | 18% | Flash indestructible, auto-attach to legend | — | — |
| 6 | Slip Out the Back | 1 | 21% | Phase out + counter | — | — |
| 7 | Lazotep Plating | 2 | -- | You + permanents hexproof | — | — |
| 8 | Winged Boots / Lavaspur Boots | 2/1 | 31/19% | Flying + ward 4 / haste + ward 1 + 1 power | — | E/haste |
| — | Dive Down, Shore Up, Octopus Form (U), Plaza of Heroes (land), Sword of Feast and Famine (13%) | | | backups | | |

### 1f. Haste (for recasting her; ~10 worth it)
**Ring of Valkas**, **Swiftfoot Boots**, Lightning Greaves, **Goro-Goro and Satoru** (UBR 3; {1}{R}
haste for the team; a recast creature that connects makes a 5/5 Dragon. Gem, unlisted), Bloodsworn
Steward, Rising of the Day (7%, +1/+0 for legends), Hero's Heirloom, Dalakos (equipped creatures get flying + haste; also mana for equips; unlisted),
Blacksmith's Talent L3, Hanweir Battlements (land).

### 1g. Extra combats (the timing fix: the second swing gets this turn's upkeep growth)
**Overpowering Attack** (5%; freerunning {2}{R} after she connects), **Aggravated Assault** (10%,
repeatable), **Karlach** (12%), Seize the Day (9%, flashback), Port Razer, Genji Glove (9%), Relentless Assault,
Full Throttle (7%). Every extra combat where she connects is another batch of upkeeps.

---

## Role 2: More upkeeps, without needing Obeka to connect

### 2a. Extra upkeep / beginning-phase sources (pool depth: **5 besides Obeka**, the entire pool)
| # | Card | MV | Type | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|---|
| 1 | **Paradox Haze** (on yourself) | 3 | Aura (player) | 40% | +1 upkeep every turn, **before combat** (Ring counters land before the attack) | Only once per turn ("first upkeep") | — |
| 2 | **The Ninth Doctor** | 3 | Creature | 22% | +1 upkeep (pre-combat) whenever he untaps in an untap step; haste, so attack with him to set it up. Retriggers in Sphinx/Shadow/Cyclonus untap steps | Must be tapped going into the untap step | C |
| 3 | **Shadow of the Second Sun** | 6 | Aura (player) | 15% | Full extra beginning phase (untap, upkeep, draw) after main 2, every turn | 6 mana; post-combat | M, D |
| 4 | Sphinx of the Second Sun | 8 | Creature | 27% | Same, on a 6/6 flier | 8 mana, creature-fragile | M, D, C |
| 5 | Cyclonus, the Saboteur | 4 | Art. creature // Vehicle | -- | 2/5 flier, connives on hit; at 5+ power converts; the Vehicle face's hit = extra **beginning phase** (untap!). Or cast converted for 7 | Needs its own connection; alternates faces | C, D |

**Extra turns at B3** ("low count, no chaining"; run at most 1–2, with no recursion): each one gives an untap, an upkeep, a draw and another
Obeka combat. Best: **Temporal Mastery** (miracle {1}{U}), Karn's Temporal Sundering (6; bounce rider;
needs a legend, which she is), Time Warp / Temporal Manipulation / Capture of Jingzhou (5). Avoid: Nexus of Fate, Lighthouse
Chronologist, Time Stretch, Walk the Aeons buyback (all chain).

### 2b. Doublers for her trigger (11 that work on her; 2 are static)
| # | Card | MV | EDHREC | What it does | Weakness | Also |
|---|---|---|---|---|---|---|
| 1 | **Roaming Throne** (name Ogre or Warlock) | 4 | 11% | Static: her trigger fires twice. 4/4 ward 2 | Psychic Paper type swap breaks it unless you name the same type | C |
| 2 | **Wizard's Staff** | 2 | 8% | Static on equipped creature: *all* her triggers x2; prowess | Equip {3} (she isn't a Wizard) | — |
| 3 | **Gogo, Master of Mimicry** | 3 | -- | {X}{X},T: copy her trigger X times (4 mana = 3 triggers) | Mana-hungry, once per untap | C |
| 4 | **Strionic Resonator** | 2 | 9% | {2},T: copy her trigger *or any upkeep trigger* | Once per untap | — |
| 5 | Echo, Perceptive Prodigy | 3 | -- | {1},T: copy a creature-source trigger (her, Dragonmaster, Prophet); vigilance 1/4 | Creature sources only | C |
| 6 | Lithoform Engine | 4 | -- | {2},T copy trigger; also copies spells | Pricier Resonator | — |
| 7 | Peter Parker's Camera | 1 | -- | {2},T: copy trigger, 3 uses | Runs out | — |
| 8 | Vantress Visions // Virtue of Knowledge | 2/5 | -- | Instant: copy trigger, then cast the Virtue later | One-shot | — |
| 9 | Return the Favor | 3 | -- | Instant: copy trigger, or redirect | One-shot | X |
| 10 | Adric, Mathematical Genius | 2 | -- | {2}{U},T: copy; sac to counter an ability | Expensive | X |

Stacking: Throne + Staff = 4x; add double strike = 8 triggers per combat.

### 2c. Obeka-independent multipliers of all upkeep triggers
- **Mirror Room // Fractured Realm** (3 // 7, --): *every* triggered ability of your permanents triggers
  twice. That covers Courts, Rings, As Foretold, Haze and her own trigger. It's the only global trigger doubler in
  UBR. Mirror Room half also copies a creature (not her: legend rule). **Top gem.**
- Strionic Resonator, Lithoform Engine, Gogo, Camera, Adric: copy any one upkeep trigger per untap.
  Extra untap steps (Sphinx, Shadow, Cyclonus) give them another use.
- Roaming Throne naming a type shared by your upkeep creatures (otherwise just Ogre).

---

## Notable rejects
- **Thassa's Intervention**: dig or counter. Gives no evasion.
- **Distortion Strike / Taigam's Strike**: the rebound copy fires in her post-combat upkeeps, so the unblockability is wasted.
- **Access Tunnel, Thieves' Tools, Escape Tunnel**: power ≤3/≤2 caps turn off once she grows.
- **Cultist of the Absolute**: +3/+3 flying deathtouch, but "sacrifice a creature" each upkeep is multiplied and eats her.
- **Clara Oswald**: 6 mana to double only The Ninth Doctor's trigger.
- **The Peregrine Dynamo**: can't copy a commander's ability.
- **Harmonic Prodigy**: Obeka isn't a Wizard. It only works with Psychic Paper naming Wizard (cute, two pieces).
- **Infinite Hourglass**: symmetric +1/+0, and its counters arrive post-combat.
- **Cryptic Coat**: has no equip ability, so it can't move to her.
- **Bedlam**: creatures can't block, for everyone. The table swings at the control player.
- **Tavern Brawler**: legal in the 99, but its upkeep pump only helps in the real upkeep. File it under card draw.
