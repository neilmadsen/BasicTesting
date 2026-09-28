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

## Round results

| round | commit | Opus + Jev avg place | wins | high-severity scanner findings |
|---|---|---|---|---|
| 1 | 61d2d5d | 2.10 | 3 | 12 |
| 2 | ec6da98 | 1.90 | 3 | 0 (turn audit: 45 confirmed findings, 17 false) |
| 3 | 6e99f25 | 2.00 | 2 | 3 cast-failed (fixed in 3b6046c); turn audit: 44 confirmed, 10 false, 7 fixed since |
| 4 | e24549e | 1.70 | 4 | decked 1, false-rescue 1 (pod01 g2 won with duplicated cards: contaminated), cast-failed 1 |
| 5 | 2ecf1ce | 2.30 | 2 | contaminated: 42 strategist calls failed on a spend limit (4 games ran on stale memos, #47); decked 1 (guard #43 not yet in), cast-stranded 1 (Vivi, both arms: #45, #46); turn audit: 71 findings, 44 confirmed, 5 false |
| 6 | f416c78 | 2.10 | 3 | cast-failed 1 (Probe, rescued: #53), Abrade never cast 3 (#52); no strategist failures; turn audit: 52 findings |

## Open

| # | layer | defect | found | notes |
|---|---|---|---|---|
| A | tagging | later steps of a scripted chain stay tagged after an earlier step fails | turn-audit | tie step tags to their preconditions, or escalate when a planned card isn't played |
| B | harness | Cascade Bluffs and other filter lands are never used (AI-blind) | hand | offer them as explicit mana actions |
| C | harness | Vivi's colour split isn't sized to the most expensive castable spell | hand | |
| H | executor | held answers spent against the HOLD line (Arcane Denial on Edgar, then Sephiroth resolved) | triage | tier 2 |
| I | executor | the confidence gate hands a correct pick back to Forge (Chaos Warp by 0.09 against 0.10) | triage | gate tuning |
| J | harness | auto-payment ignores the memo's payment plan; Izzet Signet and Cascade Bluffs unusable as filters | triage | Forge's payment |
| K | strategist | arithmetic slips: storm count, damage totals | triage | checklist |
| L | tagging | a REPLAN IF branch was not followed after the planned kill failed | triage | |
| M | harness | hold options costed from the printed cost, a 0-power Vivi counted as a source | triage | tier 3 |
| F | engine | a chosen cast sometimes fails at payment (Forge's AI; 5 cases in 30 games) | bugscan | #46 found one cause (reservations); the payment dump names the rest |
| G | harness | "Crackle with Power at X=0" was not offered late in one game | bugscan | likely the stale X (#29); re-check |
| Q | harness | under a hold, Forge's own pick can count off-colour floating mana (Vivi's split for another spell) and fail at payment; the rescue returns the card | scenario | low impact |
| O | executor | gates override memo-consistent picks when the options lack the facts (Ophidian Eye onto a creature about to die) | triage | C6 |
| P | tagging | threat tags on every permanent a threat player controls; step tags don't expire once done (a repeated equip keeps step 3) | triage | C8, C5 |
