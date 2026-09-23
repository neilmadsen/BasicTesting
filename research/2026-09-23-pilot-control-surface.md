# What the pilot decides, what it never sees, and whether it follows the plan

Three questions came out of the [strategist memo study](2026-09-23-strategist-memos.md):

- How many of the decisions for our seat does Jev actually make?
- Is the margin it needs to overrule Forge set right?
- Can the executor carry out what the memos plan?

## 1. What Jev sees

Jev answers **every** decision in the hooked kinds, with Forge's own answer as the default. Over 2,211
answers in the v2.2 arm:

| | share |
|---|---|
| Jev picked the same answer as Forge | 61% |
| Jev leaned elsewhere but under the margin, so Forge's answer stood | 8% |
| Jev overruled Forge | 31% |

(An earlier write-up said "Forge still makes 70% of the decisions". That was wrong. Most of that 70% is
Jev agreeing.)

**What it never sees.** `CountingController` is generated from Forge's API by
`pilot/tools/gen_counting.py` and sits under the pilot. It tallies every decision Forge's controller
makes for our seat, plus decisions made inside a play. `./edh sim --pilot count` runs Forge on our seat
with the tally on. Per game (12 games, Muldrotha, bracket 3):

Routed to the pilot: 587.2 controller calls a game. Nearly all of those are
`chooseSpellAbilityToPlay` priority checks; Jev is actually asked about 60–110 decisions a game.

Never seen: 242.8 a game.

| never-seen decision (per game) | count |
|---|---|
| payManaCost | 115.8 |
| playChosenSpellAbility | 33.8 |
| playSpellAbilityNoStack | 20.6 |
| (implicit) mana payment | 17.2 |
| chooseSingleStaticAbility | 15.8 |
| orderSimultaneousSa | 11.0 |
| chooseColor | 10.5 |
| chooseSingleReplacementEffect | 6.8 |
| payCostToPreventEffect | 2.9 |
| chooseCounterType | 2.7 |
| (implicit) order of our simultaneous triggers | 1.6 |
| assignCombatDamage | 1.3 |
| orderMoveToZoneList | 1.1 |
| (implicit) X value | 0.5 |

Most of the never-seen volume isn't strategic:
- `playChosenSpellAbility` and `playSpellAbilityNoStack` *execute* plays;
- colour choices for "any colour" mana are trivial;
- trigger ordering matters about 1.6 times a game;
- modes and multi-target choices barely occur in this deck.

Two unseen decisions matter:
- **Mana payment:** specifically, what gets left untapped.
- **X values:** rare, but decisive when they occur (Toxic Deluge's X against an indestructible
  board, Walking Ballista's X).

## 2. The overrule margin

The log kept only final answers, so `pilot_audit.recover_gated()` re-asked Jev, offline and exactly as
posed, the 178 decisions where it had leaned away from Forge but under the 0.15 margin. The blind judge
then compared Jev's preference with Forge's answer on 120 of them (memo hidden):

| Jev's lead over Forge's answer (non-pass decisions) | Jev better | Forge better | Jev's share |
|---|---|---|---|
| < 0.05 | 14 | 18 | 44% |
| 0.05–0.10 | 10 | 15 | 40% |
| **0.10–0.15** | **21** | **13** | **62%** |
| ≥ 0.15 (the overrules, earlier audits) | | | ~65% |

Overall it's a coin flip (55–53). Jev's lead over Forge's answer predicts quality, though:
- below a 0.10 lead, Forge's answer was better;
- between 0.10 and 0.15, Jev's was, at the same rate as the confident overrules (about 65%).

The default gate is now **0.10**. The 0.10–0.15 bin alone is only suggestive (p = 0.23); the change
rests on the monotone trend. Gated decisions now log Jev's raw preference and margin, so this can be
re-checked from any future log.

## 3. Does the executor follow the plan?

`research/plan_adherence.py` checks each start-of-turn memo against what happened that turn. It counts
the deck cards the memo says to play this turn, considering only cards we had access to and ignoring
mana sources named for payment.

| of planned plays | v2 memos | v3.1 memos |
|---|---|---|
| carried out | 28% | 48% |
| offered to Jev, but it chose otherwise | 21% | 20% |
| never offered: plan impossible | 42% | 17% |
| never offered: activation of a permanent we control | 9% | 16% |

v3's plans are far more executable, and they are carried out almost twice as often. The executor's own
divergence is steady at about 20%. Some of those cases were margin-gated, which the lower gate
addresses.

## 4. X values and held mana

Two hooks close the gap between plan and action that the census and the memo study pointed to.

- **X.** Every action option whose cost has X gets a speculative X question in the same Jev call. That
  covers mana X (Walking Ballista, Pernicious Deed) and non-mana X ("pay X life" for Toxic Deluge; Baba
  Lysaga's "sacrifice up to three"). The default is "let Forge choose". The chosen X is set on the spell
  (Forge's payment reads it) after an affordability check.
- **Held mana.** In our main phases Jev is also asked whether to keep mana open until our next turn for
  one instant-speed play. Candidates are instants and flash cards in hand, plus activated abilities of
  non-land permanents that target or counter. Each option names the exact sources it would hold. A hold
  uses Forge's own next-spell reservation, re-applied after each of Forge's priority evaluations:
  - plays that would spend held mana leave the menu;
  - the held play itself releases the mana.
- **Combat evaluation in the options.** Each attack option says how many of the defender's untapped
  creatures can block it, and how many would kill it and survive or trade. Each block option says whether
  our blocker kills the attacker and survives. Both come from `ComputerUtilCombat`.

In three games with v3 memos, Jev held mana 4 times in 57 opportunities, each time exactly what the
memo's HOLD line said:
- memo: "Keep U for Stormtamer against targeted removal on Muldrotha"; executor: "keep {U} open
  (Island) for Siren Stormtamer";
- memo: "{2} for Barrin on P1's turn"; executor: "keep 2 open (Command Tower, Forest) for Barrin".

The Island stayed untapped. Jev chose X values of Deed 3 and 4, Deluge 4 and 8, and Ballista 3.
Previously Forge had offered Ballista from hand at X = 0. That's mechanism, not win-rate evidence.

## What's left

- **Attacks** are still the one decision kind where the blind audit favours Forge (16–11 across three
  audits). The next step is adding Forge's own combat prediction to each attack option: blocked,
  killed, or unblocked.
- **The 20% of available planned plays Jev doesn't pick.** Some are sequencing (it took another planned
  play first); some are gated.
- **Game-level evidence.** No arm has yet beaten Forge on win rate over 24 games. Separating a 10-point
  difference would take about 96 games per arm on fresh pods: roughly 8–10 hours with the strategist
  and verify pass.
