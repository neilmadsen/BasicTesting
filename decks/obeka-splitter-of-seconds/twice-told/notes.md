# Obeka, Splitter of Seconds: Twice-Told (Bracket 3)

A Grixis spellbook control deck. When Obeka deals combat damage, she grants that many extra upkeep steps
after combat, and each of them counts as "your next upkeep". So every rebound spell cast before combat
damage is cast again that turn, and Galvanoth, Panoptic Mirror and the two Rings each fire once per upkeep.
On turns she doesn't connect, the deck plays draw-go: hold up a counter or removal, trade one for one, and
draw ahead.

*Revision 2* (after the critic's review): two real sweepers and an instant answer to alpha strikes, an
honest engine spec, a second Ring and the commander-damage plan written down, plainer bracket notes, and
Bojuka Bog. See "Revision 2 changes" at the end.

*Revision 3* (after the pilot-game loss diagnosis): we lost when another player's board outgrew the table, or
when several attackers bled us from 40 to about 12 with no blockers. Revision 3 adds board answers (now 8, held
by T7 in 70% of goldfish games) and four cheap bodies and deterrents (Baleful Strix, Silent Arbiter,
Propaganda, Court of Embereth's Knights). See "Revision 3 changes" at the end.

## Plan

**Survive first.** This deck wins late (turn 7–10), so its first job is not to die to the creature deck at the
table. That means:
- Bodies by turn 3–4. Propaganda taxes attacks on us. Silent Arbiter caps every player, us included, at one
  attacker and one blocker per combat, so no one can alpha strike.
- A board answer held from turn 5–6 on: Storm's Wrath, Languish, Toxic Deluge, overloaded Mizzium Mortars, a
  foretold Delayed Blast Fireball, or at instant speed Aetherize, Aetherspouts or Evacuation.
- Spot removal on the one creature that makes a board snowball (Edgar Markov, Giada).

Only then the engine. We are rarely the target; we lose when someone else's board runs away, so sweep that
board, not ours.

**How it wins (five routes, the same engine used differently):**
1. **Ring commander damage.** Ring of Evos Isle (Obeka is blue) and Ring of Xathrid (she's black) each put a
   +1/+1 counter on her in *every* one of our upkeeps, Obeka's extra ones included, so each hit makes the
   next one much bigger. Damage goes to one player, so it's 21 commander damage:
   - *One Ring, equipped before the turn:* natural upkeep makes her 3. She hits for 3, which gives 3 extra
     upkeeps and 3 counters, so she's 6. Next turn's upkeep makes her 7: she hits for 7 and grows to 14.
     The turn after, she's 15. Commander damage is 3 → 10 → 25, so that's lethal on the third hit.
   - *One Ring with World at War* (three combats in one turn): 3 + 6 + 12 = 21 in a single turn.
   - *Two Rings:* she grows by 2 per upkeep. Upkeep makes her 4; she hits for 4, which gives 4 upkeeps, +8, so
     she's 12. Next turn's upkeep makes her 14 and she hits for 14: that's 18 commander damage, and the third
     hit is overkill. Add Sword of Wealth and Power (+2) and it's 6 then 20: lethal on the second hit.
   - *Lizard Blades* (double strike): two combat-damage events, each granting upkeeps and each counting as
     commander damage. With one Ring she hits for 3 + 3 = 6, gets 6 upkeeps, and is 10 next turn, hitting for
     10 + 10 = 20 (26 total).
     Lethal on the second hit.
   - A Ring equipped in main phase 1 misses that turn's natural upkeep. The first hit is then 2, and the clock
     slows by about a turn.
2. **Mirror burn.** Imprint Delayed Blast Fireball (X = 3) or Fiery Confluence (X = 4) on Panoptic Mirror.
   The Mirror's copy is created in exile and cast from there, so Delayed Blast Fireball deals 5 to each
   opponent and each creature they control, every upkeep. On an Obeka turn with two extra upkeeps that's 15 to
   each opponent, plus 5 in every natural upkeep. Fiery Confluence is 6 to each opponent per upkeep.
3. **Doubled burn turn.** With Cast Through Time (or Ojer Pakpatiq, for instants) out, cast Breath of
   Malfegor, Maestros Charm (drain mode) and Fiery Confluence from hand before combat (Confluence, a sorcery,
   rebounds only with Cast Through Time). Connect with Obeka, then
   recast the rebounding ones free in her first extra upkeep (all three with Cast Through Time; only the two
   instants with Ojer). Archmage Emeritus draws a card and Storm-Kiln Artist makes a Treasure for every one of
   those casts.
4. **World at War turn.** Cast World at War before combat. Obeka connects, and in her first extra upkeep World
   at War rebounds, which sets up a *second* additional combat after main phase 2. That's three combats in
   all. Every one Obeka connects in grants more upkeeps: more Ring counters, more Mirror copies, and more
   Galvanoth looks (which cast only when the top card is an instant or sorcery).
5. **Control attrition.** Rebound removal kills two things per card. Theater of Horrors (on turns an opponent
   has lost life) and Archmage Emeritus generate cards. Obeka chips in, growing with the Rings, while
   Court of Ire pings and Court of Embereth's Knights add up. Slow, but it's what happens when the engine pieces get answered.

**Key turns.** T1–3: land drops, a rock, cheap selection, and hold up a counter or removal. T4: Obeka (83% on
curve in the goldfish). T5–6: a Ring and/or evasion on Obeka, then the first attack, with a rebound spell cast
precombat when you have one. T6+: Panoptic Mirror or Cast Through Time, protected by a held counter or Fierce
Guardianship.

**Mulligan.** Keep 3–4 lands with at least two colours, plus either a rock or two-mana interaction. Ideal
keep: lands, a rock, a Ring or an engine card, and a counter. Mulligan 1-landers, 6-landers, and hands with no
blue source (37% of our pips are blue). Don't keep a hand of only five-drops.

## Pilot notes

**The order of an Obeka turn (this matters):**
1. *Main phase 1:* cast from hand the spells you want doubled: rebound cards, or any instant or sorcery with
   Cast Through Time out. Ojer Pakpatiq gives rebound only to instants cast from hand.
   - Put evasion on Obeka here: Aqueous Form, Brotherhood Regalia, Key to the City ({T}, discard a card),
     Aether Tunnel, or Thassa, God of the Sea's {1}{U} unblockable ability. Menace alone often gets through
     early.
   - Equip the Rings (equip {1} each) before the turn you need them if you can: their counters come in the
     upkeeps.
   - Sword of Wealth and Power, Lizard Blades and Aether Tunnel must be on *before* combat, because each point
     of power (and double strike) is another upkeep.
   - Sword gives protection from instants and sorceries, so once it's on, our own Fantastic Elasticity and burn
     can't target Obeka either. Auras and equipment are unaffected.
2. *Combat:* Obeka connects. If Sword of Wealth and Power is equipped, it makes a Treasure and sets up a copy
   of the next instant or sorcery we cast this turn.
3. *Extra upkeeps (after combat).*
   - All rebounds fire in the *first* extra upkeep.
   - Default trigger order in each upkeep: **Thassa's scry first, then Galvanoth, then Theater of Horrors.** A
     rebounding Brainstorm also goes before Galvanoth, so the top card is chosen.
   - Resolve Theater before Galvanoth only to exile a land you want to play (the scry has shown it on top).
   - Ring counters and Court of Ire resolve in any order.
   - Mana empties between steps, so any mana you tap in an upkeep must be spent in that upkeep.
   - An instant cast from hand in extra upkeep 1 (with Cast Through Time or Ojer out) rebounds again in extra
     upkeep 2.
   - **Shortcut:** with no Galvanoth, Mirror or Theater out, and once any rebound casts in the first extra
     upkeep are done, the remaining upkeeps only add counters from equipped Rings (plus a Thassa scry and a Court
     of Ire hit each). Count N upkeeps, add N counters per equipped Ring, resolve the scries and Court hits, and
     move on.
4. *Main phase 2:* sorcery-speed follow-up with leftover lands and the Treasures made in the upkeeps
   (Storm-Kiln Artist, Unexpected Windfall, Prismari Command). Sorceries Theater of Horrors exiled
   can only be cast here, in a main phase with an empty stack; play an exiled land too if you still have a land
   drop. Once Obeka has connected, an opponent has lost life this turn, so Theater's condition is met. Its
   instants can be cast during the upkeeps themselves.

**Decking warning.** Theater of Horrors' exile is mandatory ("exile the top card", no "may"). A two-Ring Obeka
turn can mean 15–20+ upkeeps, so a few turns of that can exile 30+ cards. Count your library before a big turn,
and if it's short, let Theater be destroyed or attack a different way. Galvanoth's look is optional, and
Thassa's scry doesn't move cards out of the library.

**Key lines.**
- *Ring snowball:* equip a Ring, attack every turn she can connect, and point all the damage at one player.
  With two Rings, even a single connected hit makes the next one lethal-sized.
- *Mirror lock:* Panoptic Mirror, then {3},{T}: imprint Delayed Blast Fireball. From then on each upkeep is a
  one-sided 5-damage sweep plus 5 to each opponent. Imprint at the end of an opponent's turn to dodge
  sorcery-speed answers.
- *Cast Through Time turn:* CTT, then next turn a pile of cheap instants and sorceries from hand precombat
  (Staggershock, Electrolyze, Kolaghan's Command, Unexpected Windfall). Obeka connects. Each one that resolved
  may be recast once, free, in her first extra upkeep (not in every upkeep); Windfall still needs a discard. The
  recast is from exile, so it doesn't rebound again.
- *Ojer Pakpatiq:* on opponents' turns, the removal and draw instants we cast from hand rebound in our next
  upkeep, a free card even without Obeka connecting. **Counterspells cast under Ojer also gain rebound, but in
  our upkeep there's usually nothing to counter.** The rebound cast fizzles or is skipped, and the card stays
  in exile, so counters cast under Ojer are effectively one-use cards that don't go to the graveyard.
- *World at War:* cast it precombat only when Obeka can connect (evasion on), since the rebound and the second
  extra combat both depend on that first hit. With a Ring on, it's the 21-damage turn above.
**When to sweep (the pilot flags this as DANGER).** Sweep when any opponent's board can kill us next turn,
or can kill another player and then us, counting the power that can actually reach us past Propaganda and
Silent Arbiter. Also sweep when one board has grown past the rest of the table (Edgar Markov's vampires,
Giada's angels) even if it isn't pointed at us yet. Don't wait for the engine turn. Don't sweep a board that
isn't a threat just because the sweeper is in hand. Which one:
- *Instant, on their attack:*
  - Aetherize: all attackers to their owners' hands; tokens cease to exist, with no death triggers.
  - Aetherspouts: each attacker to the top or bottom of its owner's library (owner's choice). One put on top
    replaces its owner's next draw.
  - Evacuation: all creatures to hand, ours too; Obeka may go to the command zone instead. Best at the end of
    an opponent's turn before ours.
- *Sorcery, on our turn:*
  - Overloaded Mizzium Mortars (6 mana): 4 to each creature we don't control, one-sided.
  - Languish (-4/-4) and Storm's Wrath (4 damage): Obeka survives both if undamaged.
  - Toxic Deluge: X of 4 or less spares an undamaged Obeka (at X = 4 she's left at toughness 1).
  - Languish, Storm's Wrath and Toxic Deluge (X of 3 or more) kill our Archmage, Storm-Kiln, Galvanoth,
    Baleful Strix and unattached Lizard Blades. Ojer returns as a land. Silent Arbiter (toughness 5) survives 4
    damage and -4/-4.
- *Delayed Blast Fireball: foretell it early* (pay {2} on our turn 2–4 whenever we have the spare mana). Cast
  from exile for {4}{R}{R}, it's a one-sided 5 to each opponent and each creature they control, at instant
  speed. Cast from hand it's only 2.
- Fiery Confluence's sweep mode (1 damage three times) kills only x/3s and our own small creatures.

**Bodies and deterrents.**
- Baleful Strix trades with anything.
- Silent Arbiter stops alpha strikes for everyone: one attacker and one blocker per combat. It also makes
  menace Obeka effectively unblockable, and our own plan attacks with her alone anyway.
- Propaganda taxes every attacker {2}.
- Court of Embereth makes a 3/1 Knight in each of our upkeeps, extra ones included. With Silent Arbiter out,
  only one of our creatures can attack each combat (that's Obeka), so the Knights are blockers.

**Hold up.** On opponents' turns, keep 2 mana up for Counterspell, Arcane Denial, Drown in the Loch, Izzet Charm or
instant removal. Keep 4–5 up for **Aetherize** or **Aetherspouts** when a wide board is about to swing at us
(the DANGER case).
- With Obeka in play, Fierce Guardianship is free, so you can tap out for Cast Through Time or Mirror and still
  counter one noncreature spell aimed at it (it can't stop abilities or creature ETBs).
- Save Swan Song (enchantment, instant or sorcery only) for wipes and removal spells aimed at Obeka or the
  engine. It doesn't stop creature-based or ability-based removal.

**Answer on sight.**
- (a) Creatures that can double-block Obeka (menace) when she lacks evasion: clear them precombat with
  Staggershock (toughness 2 or less) or Fire Covenant (X damage split for X life).
- (b) Artifact or enchantment removal aimed at the Mirror, Cast Through Time or the Rings.
- (c) Stax that taxes spells (Rule of Law effects) or stops extra steps.
- (d) Anything that wins faster than our clocks.
- (e) Graveyard engines: exile the graveyard with Bojuka Bog. Note that Bog shrinks the graveyard Drown in the
  Loch counts.

**Never do.**
- Don't cast X spells as rebound or Mirror targets: a free cast has X = 0 (Memory Deluge also looks at 0 cards).
- Don't expect a free cast (rebound, Galvanoth, Mirror) of Mizzium Mortars to overload: overload is an
  alternative cost, so a free cast is the single-target mode.
- Don't count on "the next turn's upkeep" cantrips firing in Obeka's extra upkeeps: they don't.
- Don't attack Obeka into a board that kills her without a counter or protection up when the payoff is small.
- Don't use rebound card-draw on an opponent with an empty hand (Recurring Insight targets one opponent).
- Don't tap mana in an upkeep expecting to use it in main phase 2; it empties.
- Don't spread Ring-grown Obeka damage across players unless you're closing with burn: commander damage counts
  per player.

## Key cards and lines

1. **Ring of Evos Isle + Ring of Xathrid**: with both equipped to Obeka (blue and black), she gets two +1/+1
   counters in every upkeep, extra ones included, so her damage compounds.
2. **Panoptic Mirror + Delayed Blast Fireball / Fiery Confluence**: the burn clock; a copy every upkeep.
3. **Cast Through Time**: instants and sorceries cast from hand that resolve before Obeka connects may be
   recast free in that turn's first extra upkeep; the recasts don't rebound again.
4. **Galvanoth**: each upkeep, may cast the top card free if it's an instant or sorcery; Thassa, Aqueous Form,
   Brainstorm and Castle Vantress help set it up.
5. **Ojer Pakpatiq**: a 4-mana Cast Through Time for instants that comes back as a land if it dies.
6. **Sword of Wealth and Power / Lizard Blades**: more power or double strike before combat means more upkeeps.
7. **World at War**: cast from hand precombat; if Obeka connects in the first combat, its rebound in the extra
   upkeep adds a second extra combat, for three in all.
8. **Archmage Emeritus / Storm-Kiln Artist** (magecraft: cast or copy): payoffs that turn each upkeep cast
   into a card or a Treasure.
9. **Board answers: Storm's Wrath, Languish, Toxic Deluge, Mizzium Mortars, Aetherize, Aetherspouts,
   Evacuation, foretold Delayed Blast Fireball.** Eight answers, held by T7 in 70% of goldfish games. Storm's Wrath leaves an undamaged
   Obeka alive; Toxic Deluge does with X of 4 or less (6 or less with Sword of Wealth and Power, more with +1/+1 counters from
   Ring of Evos Isle or Ring of Xathrid).
10. **Court of Ire / Theater of Horrors**: Court deals 2 damage (7 while we're the monarch) in every upkeep.
   Theater exiles a card in every upkeep, playable on our turn if an opponent lost life that turn.

## Gems

(23 gems; verdicts from the revision-3 gem audit, judged in both A/B orders: 20 gem better, 2 split, 1 staple
better, defended below)

- **Ojer Pakpatiq** (vs Jhoira of the Ghitu): free recasts of our instants on demand rather than suspend's
  random delay, and it survives death as a land. *Gem better.*
- **Archmage Emeritus** (vs Phyrexian Arena): draws on every rebound, Galvanoth and Mirror cast, so an Obeka turn
  draws 3–6 cards. *Split (the verdict flipped with the A/B order; slight).*

- **Storm-Kiln Artist** (vs Izzet Signet): Treasures made in upkeeps carry into main phase 2, unlike floating
  mana, which empties. *Gem better.*
- **Panoptic Mirror** (vs Court of Ambition): a repeatable spell instead of a fixed drain; with Delayed Blast
  Fireball it sweeps and burns every upkeep. *Gem better.*
- **Sword of Wealth and Power** (vs Ring of Valkas): +2 power now, protection now, and a spell copy. *Gem better.*
- **Key to the City** (vs Trailblazer's Boots): unblockable at instant speed with no equip cost, plus a card
  draw engine. *Split (slight).*
- **Theater of Horrors** (vs Court of Vantress): exiles one card per upkeep (three when Obeka connects for 2),
  playable on later turns of ours once an opponent has lost life that turn. Watch your library (see Pilot
  notes). *Gem better.*
- **Faithless Salvaging** (vs Faithless Looting): rebound on its own, at instant speed. *Gem better.*
- **Staggershock** (vs Abrade): cast from hand before Obeka's combat damage, its rebound comes in her extra
  upkeep, so it's two 2-damage spells in one turn. *Gem better.*
- **Delayed Blast Fireball** (vs Cyclonic Rift): a one-sided sweep that becomes 5 damage from exile (Mirror,
  rebound, foretell). *Gem better.*
- **Maestros Charm** (vs Suspended Sentence): removal, drain or dig at instant speed, all in our colours. *Gem better.*
- **Breath of Malfegor** (vs Exsanguinate): no X, so it keeps its full 5 when rebound or the Mirror casts it free. *Gem better.*
- **Izzet Charm** (vs An Offer You Can't Refuse): a counter that's also removal or a loot, and its non-counter
  modes double under Ojer. *Gem better.*
- **Drown in the Loch** (vs Mana Leak): stays live late and doubles as removal. *Gem better.*
- **Fire Covenant** (vs Deadly Rollick): instant removal of several creatures we choose, for 3 mana and X life. *Gem better.*
- **Fantastic Elasticity** (vs Void Squall): 3 mana instead of 5, and its rebound can regrow a spent burn spell. *Gem better.*

- **Mizzium Mortars** (vs Blasphemous Act): a 2-mana spot kill early, and overloaded a one-sided 4-damage sweep
  that leaves Obeka and our bodies alive. Blasphemous Act would kill her. *Gem better.*
- **Languish** (vs Damnation): -4/-4 clears 4/4s and indestructible creatures but spares Obeka (toughness 5) and
  Silent Arbiter. *Gem better.*
- **Aetherspouts** (vs Cyclonic Rift): the audit judged Rift better (clear): cheap spot bounce early, a one-sided
  overload late. Kept because Rift is a Game Changer and our three slots are spent (Mirror, Fierce Guardianship,
  Demonic Tutor). Aetherspouts answers exactly the losing pattern, an alpha strike. Each attacker goes to its owner's library
  (owner's choice of top or bottom), so the best case is that it costs them a draw rather than coming straight
  back from hand. Rift for Demonic Tutor is listed under Swaps considered.
- **Baleful Strix** (vs Creeping Bloodsucker): a 2-mana flying deathtouch blocker that replaces itself; it stops
  the bleed the pilot games showed. *Gem better.*
- **Fiery Confluence** (vs Vandalblast): burn, sweep or artifact removal, and the best Mirror imprint after
  Delayed Blast Fireball. Its 3-damage sweep mode kills our own small creatures. *Gem better.*
- **Recurring Insight** (vs Rhystic Study): two refills in one turn without spending a Game Changer slot. *Gem better.*
- **World at War** (vs Relentless Assault): cast from hand precombat, its rebound in Obeka's extra upkeep adds a
  second extra combat that turn, if she connects in the first. *Gem better.*

## Omitted staples

- **Twilight Prophet** (79%): needs ten permanents for city's blessing, and this deck runs few permanents. Its upkeep drain is the Long Morning build's job.
- **As Foretold** (79%): suspend gives random, delayed free spells; rebound and Galvanoth do that on our schedule.
- **Dragonmaster Outcast** (75%): needs six lands and dies to everything; tokens don't fit a control deck.
- **Whispersilk Cloak** (41%): its shroud stops us equipping the Rings, Sword of Wealth and Power and Lizard Blades to Obeka, and stops us enchanting her with Aqueous Form. Brotherhood Regalia gives the same unblockability without shroud.
- **Replicating Ring** (74%): ramp rock that pays off slowly; plain rocks and Treasures do the job here.
- **Court of Ambition / Court of Locthwain / Court of Cunning** (73/62/46%): we run Court of Ire (removal and reach) and Court of Embereth (blockers and reach); the others are drain-or-discard, theft-casting and mill engines that suit the Long Morning build better. This deck's upkeep value comes from spells (Galvanoth, Mirror, rebound) and the Rings.
- **Creeping Bloodsucker** (68%): an upkeep drain body that doesn't block well; Baleful Strix is our cheap body.
- **Plargg and Nassari** (61%): a random, symmetrical upkeep engine at 5 mana; Galvanoth is ours alone.
- **Extravagant Replication** (61%): 6 mana and copies permanents; this deck's engine is spells and Ring counters.
- **Mechanized Production** (60%): artifact-copy plan; we have few artifacts worth copying.
- **Inspiring Refrain / Rousing Refrain** (55/46%): suspend card flow; Recurring Insight and rebound draw do this now.
- **Nightscape Familiar** (52%): a cost reducer for blue/red spells; Storm-Kiln Artist does more for a spell deck.
- **Jhoira of the Ghitu** (46%): replaced by Ojer Pakpatiq.
- **Lightning Greaves** (46%): shroud stops our own auras and equipment; Ring of Evos Isle and Brotherhood Regalia instead (Swiftfoot Boots was cut in revision 3).
- **Suspended Sentence** (45%): replaced by Maestros Charm and the rebound removal.
- **Indulgent Tormentor / Skyline Despot** (43%): five- and seven-drop creatures whose upkeep value the opponent can refuse (Tormentor) or that needs the monarch (Despot); the top end is Cast Through Time and Recurring Insight.
- **An Offer You Can't Refuse** (43%): gives opponents Treasures; Izzet Charm, Swan Song and Drown in the Loch instead.
- **Paradox Haze** (40%): adds one upkeep after our first each turn, repeating the upkeep permanents (Galvanoth, Mirror, Thassa, Theater, Court of Ire, the Rings) but not rebound or Obeka's extra upkeeps; it's on the swap list.
- **Profane Tutor** (40%): suspend 2 tutor; Demonic Tutor is our one tutor.
- **Exotic Orchard / Crumbling Necropolis / Reliquary Tower** (60/53/49%): we run true duals, shocks, fetches and a triome; Thought Vessel was cut too, and hand size hasn't been a problem.

## Testing

**Goldfish (`./edh analyze`, 10,000 trials, 36 lands, average nonland MV 2.97 in revision 3, up from 2.83).**
Obeka's average first cast is T3.9: 83% on curve, 90% by T5, colour-blocked 2%. Screw (2 or fewer lands on T4)
is 7%; flood (9+ lands seen by T7) is 2%. Ramp in hand by T4 is 77% (was 79%) after cutting Big Score, whose Treasures counted as ramp.

**Engine (`./edh engine`).** The evasion line counts only cards that say "can't be blocked", plus Silent Arbiter
in revision 3: with one blocker per combat, menace Obeka can't be blocked. Protection and hexproof don't count.
The payoffs are the 13 real doublers: rebound cards, Ojer, Cast Through Time, Galvanoth, Mirror, Sword, Theater,
Court of Ire and (revision 3) Court of Embereth.

| Block | Rev 2 | Rev 3 | Notes |
|---|---|---|---|
| **Board answer held** (`by: 7`, held 1 of the 8 answers) | 35%* | **70% by T7** | target 65–70% |
| Obeka turn armed (commander + evasion + payoff), by T6 | 42% | **48%** (43% on the rev-2 spec) | |
| Obeka + payoff (menace only), by T6 | 72% | 75% | |
| Doubling the spellbook (two payoffs), by T6 | 17% | 20% | |
| Interaction held up (2 counters/removal), by T5 | 90% | 92% | |

\*The coordinator's figure. Its list also named Cyclonic Rift, Evacuation and Blasphemous Act, none of which
revision 2 ran, so in effect it counted 3 sweepers.

- **Board answers** are Storm's Wrath, Toxic Deluge, Languish, Aetherize, Aetherspouts, Evacuation, Mizzium
  Mortars and Delayed Blast Fireball: 70% by T7, 67% by T6. That's honest only if Fireball is foretold early and
  Mortars has 6 mana to overload.
  - Without Evacuation it's 65%. Without Evacuation and Fireball, 59%.
  - The bottleneck is "not drawn" (30%). Demonic Tutor, Fact or Fiction and Recurring Insight improve it, and
    the goldfish doesn't model them.
- **The engine didn't lose ground.** On the identical revision-2 spec the armed rate is 43% against 42%, because
  none of the cuts (Sensei's Top, Preordain, Infernal Grasp, Impending Flux, Swiftfoot Boots, Negate, Big
  Score, Guttersnipe) were payoffs or "can't be blocked" evasion. Under the revision-3 spec it's 48%; the
  extra 5 points come from counting Silent Arbiter as evasion and Court of Embereth as a payoff.
- The goldfish draws one card a turn and models none of our selection and draw spells, so all of these are
  floors.

**Audits.**
- *Omissions:* 27 `!!` staples, each answered under Omitted staples. Court of Ire, Aether Tunnel and Ring of
  Evos Isle were added after the first audit. Ring of Xathrid and Brotherhood Regalia came in with revision 2.
- *Claims, revision 1:* four runs (63, then 103 claims each run), all findings fixed. Run 4 left 3 overstated, 2
  unclear and 1 "wrong" (the judge read "after Fireball" as the X-spell Fireball), all rewritten. Most findings
  were "rebound only from hand / only if cast precombat" precision.
- *Claims, revision 2* (deck + rewritten notes), 103 claims: 93 ok, 5 overstated, 5 unclear, 0 wrong. All ten
  were rewritten: Fire Covenant isn't an automatic sweep, a Ring counts only while equipped, Storm's Wrath spares
  only an undamaged Obeka, the shortcut has to leave room for rebound casts, and Theater exiles cards rather than
  drawing them. A confirming run: 97 ok, 1 overstated (fixed), 4 "unclear" that were truncated multi-line sentences
  the judge saw cut off (re-checked by hand), and 1 "wrong" where the judge read "Ring counters" as the Ring
  tempting you (reworded to name the +1/+1 counters).
- *Gems:* revision 1, run 2: 86% (24/28); two swapped, two defended. Revision 2: 21 gems, 95% gem better
  (20/21). Revision 3 (both A/B orders): first pass 25 gems, 19 better, 4 split, 2 staple better. Both "staple
  better" cards were swapped: Guttersnipe for Court of Embereth (the judge's pick twice running) and Ophiomancer
  for Silent Arbiter (clear). Final pass: **23 gems, 20 gem better, 2 split (Archmage Emeritus, Key to the City),
  1 staple better (Aetherspouts vs Cyclonic Rift, defended: Game Changer budget)**, 87% hit rate.
- *Claims, revision 3:* run 1, 103 claims: 1 wrong (tokens bounced by Aetherize "die"; they cease to exist with
  no death trigger) and 9 overstated, all fixed. The biggest was Aetherspouts: the owner chooses top or bottom,
  so it isn't a permanent answer. Run 2: 96 ok, 2 overstated (Baleful Strix vs first strike, Staggershock timing),
  both fixed. Its 5 "unclear" are multi-line sentences the judge saw cut off, re-checked by hand. Revision 2's
  audit, for the record: The one "staple better" is Guttersnipe vs Court of Embereth (slight), defended under Gems. The new
  cards (Storm's Wrath, Aetherize, Ring of Xathrid, Brotherhood Regalia, Lizard Blades, Bojuka Bog) are staples
  or plain role-players, not gems.

**Forge smoke test** (`./edh sim --bracket 3 --games 16`, `sims/20261011-063149-b3`). It ran on the revision-1
list *before* its last three swaps, and before revision 2's eight changes. No re-sim was requested. Revision 2
swaps creature-light cards for sweepers and equipment, which should help most against the creature decks we
lost to, but that is reasoning, not evidence.
- **Won 1/16 (6%, 95% CI 1%–28%; baseline 25%)**, 1 timeout/draw, 0 errored games. Average game 10.2 rounds;
  we died on round 9.9 on average, all to life loss against creature decks (Edgar Markov, Y'shtola, Giada,
  Sauron). That loss pattern matches the critic's point: only Toxic Deluge cleared 4/4s, and Forge can't cast
  Toxic Deluge.
- Commander cast in 100% of games, but first on **round 6.2** against a goldfish T3.8. The AI casts rocks and
  cheap spells first and holds Obeka.
- **The mechanism works in Forge.** Logs show Obeka connecting and the extra upkeeps resolving. Staggershock and
  Distortion Strike were cast precombat and rebound in the *same turn's* extra upkeep (pod02, game 2). Thassa's
  scry fired once per upkeep, and Cast Through Time resolved and rebounded Staggershock (pod01).
- **Never cast (12):**
  - *Flagged unplayable for the AI, so the sim is blind:* Panoptic Mirror, Fire Covenant, Toxic Deluge,
    Recurring Insight.
  - *Additional-cost draw the AI avoids:* Unexpected Windfall, Big Score.
  - *Situational:* Izzet Charm, Faithless Salvaging, World at War and Into the Time Vortex (each discarded once).
  - *Never seen in the logs:* Guttersnipe, Theater of Horrors.
  - None was cut for being uncast. Into the Time Vortex left in revision 2 for a sweeper, not because Forge
    ignored it.

**Pilot confirmation** (revision 2; `./edh sim --games 4 --pilot jev --strategist claude-cli --strategist-every 3`,
`sims/pilot-check`). Four games test mechanisms, not strength.
- **Result:** 0/4 (95% CI 0–49%). All four were lost to life total around round 10.5; Giada and Edgar Markov
  won two each. Bugscan: clean.
- **The pilot plays the deck as designed.** Obeka was cast in every game, first on round **4.0**, against Forge
  AI's 6.2. She connected 12 times in one game (double strike via Lizard Blades) and 5 times in another.
- **Every engine fired in Obeka's extra upkeeps:**
  - Court of Ire dealt 7 in consecutive upkeeps of the same turn, killing Sephara and Bruna.
  - Galvanoth looked once per upkeep.
  - Cast Through Time gave Aetherize rebound, and it was recast free.
  - A foretold Delayed Blast Fireball dealt a one-sided 5 to every opposing creature and player.
- **What didn't happen:** neither Ring was cast in four games (so Obeka always hit for 2), and nor were Storm's
  Wrath, Panoptic Mirror or Sword. That's partly the draws, and partly that the deck spent its early turns on
  interaction.
- **The losses look like the Forge losses:** go-wide angel and vampire boards outracing a deck whose kill comes
  online around turn 7–9. Revision 2's sweepers help only when drawn. If your table is creature-heavy, the first
  swaps to consider are under Swaps considered: more cheap blockers or another sweeper.

## Bracket

`./edh validate deck.txt --bracket 3`: **PASS**. Game Changers (3): Panoptic Mirror, Fierce Guardianship,
Demonic Tutor. No two-card combos detected; Commander Spellbook's deck tag is "Powerful (≈bracket 3+)", from
card power, not combos. No REVIEW items.

**Rule-0 talking point: Panoptic Mirror + Delayed Blast Fireball is a lock.** Say this before the game.
- It's legal at bracket 3: not infinite, two cards, 8 mana over at least two turns. Demonic Tutor can find
  either half.
- Once it's set up, every one of our upkeeps deals 5 to each opponent *and* 5 to each creature they control.
- A creature deck can't play through it: anything with toughness 5 or less dies before it can attack. The table
  has to answer the Mirror (an artifact) or race it.
- Obeka's extra upkeeps make it 10–15+ per opponent per turn.
- It's the strongest thing the deck does. If the table finds it too much, imprint Fiery Confluence instead (6 to
  each opponent, no sweep) or leave the Mirror out (Paradox Haze or Rhystic Study are the swaps).

Other review questions:
- *Is World at War an extra-turn effect?* No, it's extra combats. It can give three combats in a turn, but only
  once per game unless recurred (Fantastic Elasticity can regrow it). No loop exists in the deck. With a Ring it's
  a one-turn commander kill (3 + 6 + 12 = 21), which is worth mentioning too.
- *Ring snowball:* two equipment that make each Obeka hit compound is a fast clock (two hits with two Rings and
  Sword). It's the crowd's own plan with this commander, and it dies to removal and blockers like any voltron.
- *Spirit of the bracket:* three Game Changers, a lock, and efficient interaction put the deck at the strong end
  of bracket 3. It has no fast combo kill; the realistic win is turn 7–10.

## Swaps considered

Revision 3 cuts, with why each was the lowest-value slot:
- **Sensei's Divining Top** and **Preordain**: card selection. Thassa, Aqueous Form, Brainstorm and Castle
  Vantress still set up Galvanoth.
- **Infernal Grasp**: our ninth spot creature removal. The deck still has Terminate, Bedevil, Lightning Bolt,
  Feed the Swarm, Chaos Warp, Kolaghan's Command, Maestros Charm, Fire Covenant and Drown in the Loch.
- **Impending Flux**: a "sweeper" that rarely kills a 4/4 (X = 1 + spells cast from outside the hand).
- **Swiftfoot Boots**: Ring of Evos Isle already gives hexproof on demand, and haste rarely matters for Obeka.
- **Negate**: one counter too many. Four hard counters remain (Counterspell, Arcane Denial, Swan Song, Fierce
  Guardianship), plus Izzet Charm and Drown in the Loch.
- **Big Score**: the second copy of Unexpected Windfall.
- **Guttersnipe**: reach. Court of Embereth was judged better twice, and it makes blockers.

Swap candidates for your table:
- **Ophiomancer** (tried in revision 3): a deathtouch Snake in every upkeep, everyone's, whenever we have none.
  The gem audit preferred Silent Arbiter clearly. Ophiomancer is the swap if your table has fliers and few big
  attackers.
- **Cyclonic Rift** for Demonic Tutor: overload is the best one-sided board answer in our colours, but it costs
  a Game Changer slot.
- **Massacre Wurm**: a 6/5 body plus -2/-2 to the opponents' board. Great against tokens, not against 4/4s.
- **Blasphemous Act / Damnation**: cheaper or harder resets that kill Obeka too (recast her at +2 tax). Worth it
  only if your table is very creature-heavy.
- **Guttersnipe** back for Court of Embereth if you want reach over board presence.

- **Quantum Misalignment** (cut in revision 2): non-legendary Obeka copies, twice. It can't target a
  Sword-equipped Obeka (protection from sorceries), and the slot went to Storm's Wrath.
- **Into the Time Vortex** (cut in revision 2): two cascades for 5; the slot went to Aetherize.
- **Transpose** (cut in revision 2): rebound loot plus a pinger; the slot went to Ring of Xathrid.
- **Psychic Paper → Brotherhood Regalia** (revision 2): same effect, ward {2} instead of {1}, equip {1} for a
  legendary creature instead of {2}. A strict upgrade I found while re-pointing gem comparisons.
- **Combat Research → Lizard Blades** (revision 2): Combat Research added +1 power and a card per hit; double
  strike doubles both the upkeeps and the commander damage per hit. Combat Research is the swap back if you want
  card draw.
- **Paradox Haze** for Key to the City: a second upkeep every turn for Galvanoth, Mirror, Theater, Court of
  Ire and both Rings, even when Obeka doesn't connect. Strong with the Rings.
- **Thousand-Year Storm** for World at War: rebound casts in the upkeeps count as later spells and get copied
  more. Huge when it works, but it's a second 6+ mana do-nothing beside Cast Through Time.
- **Rhystic Study** or **Mana Drain** for Demonic Tutor, if you prefer card flow or tempo to consistency (the
  Game Changer budget is full).
- **Spellbinder** (imprint an instant, cast a copy free on each Obeka hit) for Key to the City: more payoff,
  but equip {4} is heavy.
- **Veyran, Voice of Duality** for Storm-Kiln Artist: triggers caused by casting or copying an instant or
  sorcery (Archmage, Storm-Kiln) trigger an additional time; it does nothing for upkeep triggers.
- **Hour of Devastation** for Storm's Wrath: 5 damage and no indestructible, but it would kill an Obeka without
  Ring counters.
- **Boltwave / Prisoner's Dilemma** for more fixed burn if your table plays slow.
- **Distortion Strike / Consuming Vapors**: cut in revision 1 after the gem audit.
- **Thought Vessel** back for Mind Stone if hand size becomes a problem.

## Revision 2 changes

| Out | In | Why |
|---|---|---|
| Quantum Misalignment | Storm's Wrath | A sweeper that clears 4/4s and leaves Obeka alive |
| Into the Time Vortex | Aetherize | An instant answer to an alpha strike, fits draw-go |
| Transpose | Ring of Xathrid | A second compounding Ring (Obeka is black) |
| Swamp | Bojuka Bog | Graveyard hate |
| Psychic Paper | Brotherhood Regalia | Same role, cheaper equip for Obeka, ward {2} |
| Combat Research | Lizard Blades | Double strike doubles upkeeps and commander damage |

Brief: the engine evasion line now counts only "can't be blocked" cards, and a menace-only block was added for
reference.

## Revision 3 changes

| Out | In | Why |
|---|---|---|
| Sensei's Divining Top | Baleful Strix | A cheap blocker that draws; stops the bleed |
| Preordain | Mizzium Mortars | A one-sided 4-damage sweep (overload), or early spot removal |
| Infernal Grasp | Aetherspouts | An instant, permanent answer to an alpha strike |
| Impending Flux | Languish | A real sweeper of 4/4s that spares Obeka |
| Swiftfoot Boots | Propaganda | Attack tax; go-wide boards attack someone else |
| Negate | Silent Arbiter | One attacker per combat for everyone; makes menace Obeka unblockable (replaced Ophiomancer after the gem audit) |
| Big Score | Evacuation | An instant reset of every creature; tokens die |
| Guttersnipe | Court of Embereth | Knights as blockers in every upkeep; the gem audit's pick twice |

Brief: added a "Board answer held" engine block (`by: 7`). Silent Arbiter counts as evasion, and Court of
Embereth as a payoff.
