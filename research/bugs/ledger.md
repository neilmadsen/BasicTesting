# Bug ledger: the Vivi pilot

Every defect found in the Vivi bug hunt, grouped by root cause. How each was found:
- `bugscan`: log invariants, no model calls;
- `scenario`: a Forge board replayed in seconds;
- `turn-audit`: a model reviews the turns that matter;
- by hand.

Layers:
- **engine:** Forge's rules or AI.
- **harness:** decisions the pilot never sees, or answers not applied as chosen.
- **tagging:** the memo's plan reaching the executor.
- **executor:** Jev's choices.
- **strategist:** the memo itself.

## Fixed

| # | layer | defect | found | fix |
|---|---|---|---|---|
| 1 | tagging | a card named by nickname went untagged; a fallback was tagged as the plan | hand | 29c51a4 |
| 2 | harness | a hold hid the plays that would spend the held mana | hand | be0143d |
| 3 | harness | transient API errors not retried, so Forge passed a whole main phase | hand | ac1b33e |
| 4 | harness | Vivi's mana was never offered, so overload and big X were impossible | hand | 530075c |
| 5 | harness | Vivi's once-per-turn mana ability was usable repeatedly | hand | 530075c |
| 6 | tagging | commentary was tagged as a plan; a hold was tagged as a play | hand | 61d2d5d |
| 7 | tagging | a play after a mana clause went untagged ("for {C}, then cast X"), 22 plays in 119 memos | hand | ce6ab11 |
| 8 | harness | counterspells targeted the spell's card, not the spell, and did nothing (4 of 6) | hand, bugscan | cb08b20 |
| 9 | engine | Forge's AI chose nothing for a Curiosity Aura on a 0-power creature, stranding Ophidian Eye and Sigil of Sleep cast on Vivi (0 triggers in 24) | bugscan, scenario | cb08b20 |
| 10 | harness | modal trigger targets (Hullbreaker Horror) were never asked | hand, turn-audit | ec6da98 |
| 11 | executor | Vivi's mana was made with nothing to spend it on | bugscan | ec6da98 |
| 12 | executor | memo-ordered attacks needed the big margin; a blanket "No attacks" reached no attacker | hand | ec6da98 |
| 13 | executor | the equipment cap of one blocked a move and a move back | hand | ec6da98 |
| 14 | tagging | Brainstorm put-backs and discards had no memo tags | hand, turn-audit | ec6da98 |
| 15 | harness | soulbond pairing and Aura attachments missing from the state | hand | ec6da98 |
| 16 | strategist | draw triggers not counted against the library (decked with a won game); a keyword rule read backwards (the Ring) | hand, turn-audit | ec6da98 (checklist 4d) |

| 17 | harness | multi-card effect discards (Frantic Search, Faithless Looting) went to Forge | hand, turn-audit | 5902c93 |
| 18 | executor | a planned card was played in the mode the memo doesn't want (single-target Rift for an overload) | bugscan | 68478ad |
| 19 | harness | the pass option didn't say that floating mana would be lost | bugscan | 68478ad |
| 20 | harness | storm copies were aimed by Forge, all at one 1/1 (four of five fizzled) | turn-audit | b4f8bd6 |
| 21 | harness | "up to X targets" was aimed by Forge at one target (X=2 Crackle with Power left a lethal second target) | turn-audit | b4f8bd6 |
| 22 | harness | no priority with our own spell on the stack, when the memo planned a response | turn-audit | 4a9d20b |
| 23 | tagging | an Equip activation got the step that casts the Equipment; a HOLD line's reference-only mention got a hold tag | turn-audit | f2d281c |
| 24 | harness | the option scan's 1.5 s budget dropped cards scanned last under load (Niv-Mizzet, Parun absent at random) | scenario | 68e53fa |
| 25 | tagging | regression from #18: "Cast Cyclonic Rift overloaded" not read as an overload, so the winning overload Rift was vetoed; inline "2." steps not split | triage | 6e99f25 |
| 26 | executor | Jev declined Forge's chump block against a lethal attack (two losses) | turn-audit, triage | 6e99f25 |
| 27 | executor | a later plan step played while an earlier one was on offer | turn-audit, triage | 6e99f25 |
| 28 | engine | a cast that failed at payment stranded the card in the stack zone for the rest of the game (Forge only recovers casts from the stack) | triage, bugscan | 6e99f25 |
| 29 | harness | a stale X left by Forge's AI hid X spells from the options | triage | 6e99f25 |
| 30 | harness | modal spells' modes were never asked; Forge's AI chose no tier for Fire Magic (3 of 4 did nothing) | turn-audit, scenario | 6e99f25 |
| 31 | tooling | the auditor's false positives (17 of 63): turn view hid options and gating; no card texts | triage | f4d7990 |
| 32 | engine | Forge reports every cast as played, so the stranded-card rescue never ran (Vivi herself was stranded on turn 9 and never cast again) | bugscan, turn-audit | 3b6046c |
| 33 | harness | Vivi's mana was not made when only the colours fell short (Ponder with Vivi as the only blue source) | bugscan | 3b6046c |
| 34 | harness | a mode with an unaffordable additional cost was chosen (Fira with 2 mana) | bugscan | 3b6046c |
| 35 | executor | a counterspell was cast at a spell that can't be countered (opponent's copy of Hexing Squelcher) | bugscan | d0483bc |
| 36 | executor | held answers spent against the HOLD; keep-tagged cards put back; memo-aligned picks gated away | triage | 1f95a5c |
| 37 | harness | my rescue (#32) fired on casts waiting in a frozen stack and duplicated three cards in one game (Jeska's Will cast three times) | bugscan (false-rescue) | 28deeee |
| 38 | engine | Forge's AI reserved mana for a creature it predicted after combat, so our main-1 casts failed at payment (Ponder, Hullbreaker Horror) | triage, scenario | 28deeee |
| 39 | harness | Vivi's mana was offered only from 2; plays only her mana could pay for were hidden; "nothing needs this mana" ignored non-hand plays | triage, scenario | 28deeee |
| 40 | harness | a stale warded target (Sauron) made Snap look unaffordable, so it was never offered | triage, scenario | 28deeee |
| 41 | executor | the wrong-mode veto forced a pass when the memo's mode wasn't available this turn | triage | 28deeee |
| 42 | tagging | plan steps timed for an opponent's turn were tagged as plays in our own windows (Rift in the wrong combat) | triage | 28deeee |
| 43 | executor | a draw-on-damage chain decked us after the memo set a library floor (pings followed threat tags to the face) | bugscan | c11f235 |
| 44 | engine | a failed AI payment leaves the stack frozen; every later cast of the phase waited off the stack. The real cause of #37's "burst" | bugscan (stale-freeze), Forge source | 1d06954 |
| 45 | harness | #37's fix skipped every rescue on a frozen stack, and a commander cast marks a copy skipped: Vivi stranded in the stack zone for all of pod01 g2, both arms | bugscan (cast-stranded), turn-audit | 1d06954 |
| 46 | engine | evaluating a chainable damage spell (Grapeshot) reserved the next spell's lands; the chosen Vivi then failed "Didn't find what to pay for {U}", and later options could look unaffordable. Proven by the payment dump in a pod replay | bugscan, diagnostic replay | 1d06954 |
| 47 | harness | a failed strategist kept its old memo with full authority: 42 calls hit a spend limit in round 5, 26% of decisions ran on memos 2+ turns old, and their HOLD lines declined the named plays 100 times | triage | 8af0fcc |
| 48 | harness | every multi-card discard offered 1-3 cards too few: the options were built from the list Forge's AI had sorted and removed its picks from | triage, scenario | 8af0fcc |
| 49 | tagging | a card after a disposal verb read as played ("Discard Fire Magic first, then Archmage"), and the keep rule overruled a unanimous discard; "(... tax 2)" read as step 2 | triage | 8af0fcc |
| 50 | tagging | plays timed for an opponent's combat fired in our own (our combat was labelled only "instant-speed window"); "Next turn:" bullets inside THIS TURN tagged as this turn | triage | 8af0fcc |
| 51 | harness | a hold was dropped for a play Vivi's {0} mana could pay; Vivi (our turn only) offered as a source to hold until the next turn | triage | 8af0fcc |
| 52 | harness | a modal spell cast in a mode Forge's AI didn't pick had no target: "Abrade - Couldn't add to stack, failed to target" (3 times in round 6, both arms) | bugscan (chosen-play-not-made), scenario | 74b95e4 |
| 53 | harness | hold arithmetic counted held lands as 1 mana each (Resonating Lute makes 2) and trusted Forge's affordability under a hold: Gitaxian Probe and Opt failed at payment | bugscan (cast-failed), scenario | 74b95e4 |
| 54 | harness | Vivi's mana was offered 9 times and made twice under Linvala, Keeper of Silence (canPlay() skips static bans) | triage, scenario | 03ba106 |
| 55 | tagging | regression of #49: "Never discard Negate" and "discard ... and keep An Offer" read as discards (Jev discarded An Offer and Counterspell) | triage | 03ba106 |
| 56 | executor | a later plan step answered our own earlier spell on the stack (Opt over Hexing Squelcher; P4 survived at 4 and killed us) | triage | 03ba106 |
| 57 | executor | gates: Jev's earlier plan step lost to Forge's later one at the ordinary margin; Forge's pass on a card its AI can't play counted as a judgement | triage | 03ba106 |
| 58 | tagging | threat ranks on every creature of the threat player, none on the player: 8 Niv-Mizzet pings into a 9/9 Zacama against "pings at P1's face" and "never ping Dinosaurs" | triage | 03ba106 |
| 59 | tagging | "Hold priority and cast X" tagged X as a hold; a timed-step check read the wrong quote | triage | 03ba106 |
| 60 | harness | holds priced at printed cost (Stormcatch Mentor's discount ignored; ledger N) | triage | 03ba106 |
| 61 | harness | a double-faced card's back face was offered under the front's name and took its plan tag: Harnfel cast instead of Birgi | bugscan (chosen-play-not-made), scenario | 0c77bd7 |
| 62 | executor | the HOLD-reservation veto read the counterspell's own name as the threat ("untapped for Negate"): Negate held back from Sanguine Bond (lost pod04-g1, round 7), Swan Song from Akroma's Will (round 6) | triage | c0c795a |
| 63 | harness | #52 incomplete: a modal spell's target was asked only when Jev's mode differed from Forge's, and never with one legal mode (3 of 3 Abrades hit targets the memo didn't name) | triage, scenario | c0c795a |
| 64 | executor | any plan-tagged play overruled Forge's wait in our upkeep and draw step: all 6 such plays jumped main-phase steps (Abrade before Niv-Mizzet) | triage | c0c795a |
| 65 | executor | a done plan step stayed tagged, and the plan-order rule forced it again (Greaves re-equipped twice on a kill turn; ledger P) | triage | c0c795a |
| 66 | harness | a hold decided before a draw spell found lands was never re-asked; the planned Vivi cast read as spending held mana | triage | c0c795a |
| 67 | tagging | regression of #65: after a card's first play every later option for it read "already played", hiding a planned flashback (4 Vivi mana lost) and a Greaves move-back | triage | ef8c290 |
| 68 | harness | "untap up to N lands" asked blind over every tapped land on the table: 3 of 6 untaps untapped nothing, one an opponent's land | triage, scenario | ef8c290 |
| 69 | harness | the loop breaker keyed on the question only: the 9th Ophidian Eye draw trigger of a kill turn went to Forge's "no" (7 draws, 7 pings lost) | triage | ef8c290 |
| 70 | harness | the "nothing needs this mana" check counted Vivi's mana twice, so it never fired (3 of 4 wasted activations) | bugscan, triage, scenario | ef8c290 |
| 71 | harness | a "yes" to Braids with one candidate sacrificed nothing (Forge's follow-up declined again) | triage | ef8c290 |
| 72 | harness | Vivi's colour split ignored which colours the untapped lands make: 1 mana came out red, the planned Sigil of Sleep uncastable (ledger C) | triage, scenario | ef8c290 |
| 73 | tagging | a HOLD about an untapped land ("an Island untapped") kept Island cards in hand, and Counterspell was discarded instead | triage | ef8c290 |
| 74 | harness | one blocker picked for two attackers: the second block was dropped silently | triage | ef8c290 |
| 75 | harness | ledger J: Forge's payment can't pay a filter's cost (Izzet Signet) from floating mana and spend its output, and its affordability check hid such plays; Jeska's Will, Chaos Warp and Fire Magic failed at payment in round 9 | bugscan, scenario | b34eac9 |
| 76 | harness | a mode's additional cost (Fira's {2}) wasn't counted when deciding to make Vivi's mana before paying | bugscan | b34eac9 |
| 77 | tooling | bugscan false positives: a countered spell reanimated later read as "resolved anyway"; an opponent's own Ophidian Eye read as ours | bugscan | b34eac9 |
| 78 | harness | an X answer was checked with Forge's affordability, which can't see Resonating Lute's 2-mana lands: Jev's lethal X=5 Crackle with Power became X=3, and we died next turn (pod02-g1, round 9) | triage | 24e526e |
| 79 | tagging | #67 incomplete: the done-step key ignored the verb, so playing Fiery Islet marked its planned draw activation as done (a win-attempt draw hidden twice) | triage | 24e526e |
| 80 | tagging, executor | Hullbreaker's triggers ignored the memo's own targets: trigger targets had no plan tags, a planned self-bounce needed the big margin, and sibling triggers repeated each other's targets (two kill turns lost in one game) | triage | 24e526e |
| 81 | harness | "choose one or both" modes (Jeska's Will, Flame of Anor) were left to Forge; 3 of 7 went against the memo | triage, scenario | 24e526e |
| 82 | harness | the state lacked floating mana, "mana ability used this turn" and "summoning sick" | triage | 24e526e |
| 83 | tagging | the keep rule read a HOLD line before an explicit put-back of the same card (6 of 6 keep overrules went against the memo) | triage | 24e526e |
| 84 | executor | Jev passed a main phase with floating mana and this-turn-only plays on offer (6 mana and 4 rocks lost) | triage | 24e526e |
| 85 | harness | a lower X than Forge's kept Forge's targets for its own X: an X=1 Crackle with Power held four targets and failed to target | bugscan, scenario | 05c8818 |
| 86 | harness | a filter's colours (Izzet Signet) counted as covering a spell's pips, so Vivi's mana wasn't made for Sink into Stupor's {U}{U} | bugscan | 05c8818 |
| 87 | harness, executor | an opponent's combat at us reached the pilot only if Forge's AI wanted to act, and a card both planned and HOLD-named was treated as merely held: the planned Slip Out the Back never came and the attack killed us (pod05-g1, round 10) | triage, scenario | this commit |
| 88 | tagging | regression of #83: "put back X, never Y" read Y as put back (Jeska's Will sent back before the kill turn) | triage | this commit |
| 89 | harness | #80 incomplete: a trigger could take the target of our own spell on the stack (Sigil of Sleep fizzled Chaos Warp; Hullbreaker fizzled Sink into Stupor) | triage | this commit |
| 90 | harness | regression of #75: floating mana was ignored when deciding colours, so Vivi's once-a-turn mana was made early (7 instead of 9) | triage | this commit |
| 91 | executor | #84 inert: the pass guard keyed on a label Jeska's Will's exiled cards never carried; Sol Ring from exile lost on a kill turn | triage | this commit |
| 92 | executor | the library guard fired for any draw engine on the board: an optional Ophidian Eye on Vivi redirected all 7 Grapeshot copies from a player on 4 | triage | this commit |
| 93 | harness | cleanup discards of more than one card went to Forge (Shivan Reef, Veyran and Swan Song at once) | triage | this commit |

## Round results

| round | commit | Opus + Jev avg place | wins | high-severity scanner findings |
|---|---|---|---|---|
| 1 | 61d2d5d | 2.10 | 3 | 12 |
| 2 | ec6da98 | 1.90 | 3 | 0 (turn audit: 45 confirmed findings, 17 false) |
| 3 | 6e99f25 | 2.00 | 2 | 3 cast-failed (fixed in 3b6046c); turn audit: 44 confirmed, 10 false, 7 fixed since |
| 4 | e24549e | 1.70 | 4 | decked 1, false-rescue 1 (pod01 g2 won with duplicated cards: contaminated), cast-failed 1 |
| 5 | 2ecf1ce | 2.30 | 2 | contaminated: 42 strategist calls failed on a spend limit (4 games ran on stale memos, #47); decked 1 (guard #43 not yet in), cast-stranded 1 (Vivi, both arms: #45, #46); turn audit: 71 findings, 44 confirmed, 5 false |
| 6 | f416c78 | 2.10 | 3 | cast-failed 1 (Probe, rescued: #53), Abrade never cast 3 (#52); no strategist failures; turn audit: 52 findings |
| 7 | 3578198 | 1.70 | 4 | cast-failed 1 (Fire Magic via Izzet Signet from floating mana: open J), Harnfel for Birgi (#61); Jev-only arm: no high or medium findings besides loop-breakers; turn audit: 61 findings |
| 8 | c0c795a | 1.75 (8 games) | 2 | contaminated: 33 strategist calls failed on the spend limit (5 games from mid-game), pod 5 lost to a container restart; Jev-only arm: no high or medium findings for the second round running; turn audit: 58 findings |
| 9 | d750d4f | 1.60 | 7 | cast-failed 3 (filter mana: #75, rescued), 2 scanner false positives (#77); no strategist failures; Jev-only arm: 1 medium (wasted mana) |
| 10 | d7d881c | 1.90 | 3 | cast-failed 1 (Sink into Stupor, rescued: #86), Crackle failed to target (#85); no strategist failures; Jev-only arm: 1 medium (wasted mana) |

## Open

| # | layer | defect | found | notes |
|---|---|---|---|---|
| A | tagging | later steps of a scripted chain stay tagged after an earlier step fails | turn-audit | tie step tags to their preconditions, or escalate when a planned card isn't played |
| B | harness | Cascade Bluffs and other filter lands are never used (AI-blind) | hand | offer them as explicit mana actions |
| H | executor | held answers spent against the HOLD line (Arcane Denial on Edgar, then Sephiroth resolved) | triage | tier 2 |
| I | executor | the confidence gate hands a correct pick back to Forge (Chaos Warp by 0.09 against 0.10) | triage | gate tuning |
| J | harness | auto-payment ignores the memo's payment plan; Cascade Bluffs unusable as a filter (Signets: #75) | triage | Forge's payment |
| K | strategist | arithmetic slips: storm count, damage totals | triage | checklist |
| L | tagging | a REPLAN IF branch was not followed after the planned kill failed | triage | |
| M | harness | hold options costed from the printed cost, a 0-power Vivi counted as a source | triage | tier 3 |
| F | engine | a chosen cast sometimes fails at payment (Forge's AI; 5 cases in 30 games) | bugscan | #46 found one cause (reservations); the payment dump names the rest |
| G | harness | "Crackle with Power at X=0" was not offered late in one game | bugscan | likely the stale X (#29); re-check |
| R | harness | Resonating Lute's 2-mana land ability is invisible to the option scan and holds: Arcane Denial never offered with one land (pod02-g1, round 8) | triage | moderate |
| S | harness | Mizzix's Mastery's free casts are left to Forge's AI (playSaFromPlayEffect isn't hooked): 3 of 7 copies never cast | triage | round 9 |
| Q | harness | under a hold, Forge's own pick can count off-colour floating mana (Vivi's split for another spell) and fail at payment; the rescue returns the card | scenario | low impact |
| O | executor | gates override memo-consistent picks when the options lack the facts (Ophidian Eye onto a creature about to die) | triage | C6 |
| P | tagging | threat tags on every permanent a threat player controls; step tags don't expire once done (a repeated equip keeps step 3) | triage | C8, C5 |
