# Why the pilot lost 23 of 24: a post-mortem of the v3.1 arm

Follow-up to [the control-surface study](2026-09-23-pilot-control-surface.md). The v3.1 arm (Jev executor,
Opus strategist with the v3 memo format) won 1 of 24 games on the six seed-11 pods, against 5 of 24 for
Forge's own AI with the same deck. The question: bad decisions, bad strategy, or something else?

## Short answer

**Mostly bad execution of plans that were right.**

Reviewers found 126 mistakes, 22 of them game-losing, and put 97 on the executor. In the 12 games where
the strategist worked throughout, the memo in force had named the better play in 46 of the 56
execution mistakes.

We traced every mistake to the logged decision that caused it. The causes were concrete and mostly
fixable:
- Forge's AI made resource choices that the pilot never saw: what to sacrifice, X values, shock payments,
  and the command-zone move.
- Jev overruled Forge in three kinds of decision where its overrules are reliably wrong: mulligans,
  sending attackers Forge keeps home, and discards.
- Option labels hid the information needed to follow the plan.

Strategy mattered less. The strategist made 10 mistakes and none was game-losing. The deck has one
real weakness against this gauntlet (below).

**The 1-in-24 is also not a clean measurement.** Two faults inflated the loss count, and both are now
fixed:
- **Dead strategist.** In 11 of 24 games (pods 04–06 and part of pod04-g2), the strategist's Claude calls
  hit the session limit. The error text ("You've hit your session limit") was stored as the memo, so
  those games ran with no plan. The cause was running offline memo-lab experiments at the same time as
  the arm. Model calls now fail loudly (`edhkit/claude_cli.py`): the previous memo is kept, and the sim
  report warns.
- **Backwards mulligans.** Every one of Jev's mulligan overrules across both arms went the wrong way.
  It kept 0–1-landers and shipped 3–5-landers, because the question showed card names and lands carry
  no rules text. Fixed in c0b3895.

On the 12 clean games (pods 01–03), the arms stand at: Forge 3, v2.2 2, v3.1 1. No arm is distinguishable
from another at this sample size.

## Method

1. **Digests.** `research/game_digest.py` merged Forge's game log with the pilot's decision log into one
   turn-by-turn digest per game: memos, boards, overrules, holds, X choices and escalations.
2. **Reviews.** Six reviewer subagents (Opus 5.5) each read one pod's four digests as an expert
   Commander player. For each game they listed the mistakes with turn, what happened, the better play,
   the layer responsible and a severity. They also rated how winnable the game was, from 0 to 3.
3. **Mechanism audit.** Two more subagents took every executor, Forge and mulligan mistake back to the
   decision log. For each one they found the question as posed: every option, Forge's default, Jev's
   pick and the memo in force. Each mistake got one proximate mechanism. The auditors also listed
   structural patterns across the logs that the reviewers hadn't flagged.

**Caveats.**
- The reviewers are LLMs reading digests, not a panel of players.
- They see the memo, so they may treat divergence from it as error.
- The auditors caught five places where a review contradicted the log. The biggest: "Forge kept the
  bad hand" was really Jev overruling Forge's mulligan.

Data: `2026-09-24-postmortem-data/`, holding the reviews, the mechanism audits, the digests and the
offline A/B below.

## What went wrong, by layer

| layer | mistakes | game-losing | major | minor |
|---|---|---|---|---|
| executor (Jev + Forge's defaults) | 97 | 18 | 47 | 32 |
| strategist | 10 | 0 | 5 | 5 |
| Forge (reviewers' label for choices Forge made unasked) | 9 | 2 | 6 | 1 |
| mulligan | 6 | 2 | 3 | 1 |
| deck | 4 | 0 | 2 | 2 |

Winnability as the reviewers rated it:

| rating | games |
|---|---|
| 0: nothing to be done | 1 |
| 1: long shot | 13 |
| 2: realistic chance | 9 |
| 3: should have won | 1 |

With good play, perhaps a third of the ten 2–3 games convert. That is roughly the 25% baseline, and
about what Forge's AI manages. This deck is not a gauntlet-crusher at bracket 3, but it shouldn't
lose 23 of 24.

## Why: the mechanisms

Proximate mechanism of the 112 executor, Forge and mulligan mistakes:

| mechanism | all | game-losing | what it means |
|---|---|---|---|
| Jev overruled Forge, wrongly | 45 | 8 | Jev's pick was the mistake |
| Jev agreed with Forge's bad answer | 28 | 4 | nobody caught it |
| gated | 17 | 6 | Jev preferred something else but under the margin, so Forge's answer stood |
| unhooked | 16 | 3 | Forge decided without asking |
| not offered | 3 | 1 | the right play wasn't among the options |
| sequencing / strategist | 3 | 0 | |

Pods 01–03 and pods 04–06 split differently:
- **Pods 01–03 (memos working).** Unhooked choices and gating account for 6 of the 10 game-losing
  mistakes. In 46 of 56 mistakes the memo in force named the better play.
- **Pods 04–06 (mostly no memo).** Jev's own overrules dominate (27 of 56), which is what an executor
  with no plan looks like.

### 1. Resource choices Forge made silently

These were the largest single cause of lost games when the plan was sound.

- **Sacrifice costs.** Forge's AI pays its own costs with a fresh `AiCostDecision`, never through the
  controller. So the pilot's sacrifice-cost hook had never fired, in any arm. In pods 01–03, costs
  consumed 25 of our lands, and in one turn Claws of Gix ate six:
  - Claws of Gix: 11 of 13 sacrifices were lands.
  - Barrin: 8 of 11 were lands, plus Kaya's Ghostform once.
  - Braids's end-step sacrifice: 6 of 12 were lands, plus Sol Ring twice. The yes/no was asked; the
    pick was not.
- **X.** All five Toxic Deluges resolved at X≈0; the memos asked for 4–10. All three Pernicious Deed
  activations used every available mana. One of them, at X=7, killed our own Muldrotha when the memo
  said X=4. (X was hooked after this arm ran; see the control-surface study.)
- **Shock lands and fetches.** In pods 01–03, 10 of 27 fetches produced no mana that turn: Jev fetched
  a Triome, or Forge silently declined the shock's 2 life. An untapped option was on offer every time.
  Three times this made the memo's key spell unaffordable, including a game-losing Massacre Wurm.
- **Kaya's Ghostform** fizzled 2 of 2 times: Forge moved Muldrotha to the command zone before the
  return trigger resolved.

### 2. Overrules in three decision kinds that are reliably wrong

- **Mulligans:** 10 of 10 overrules inverted, as above.
- **Attacks Forge wouldn't make.** Blind judges preferred Forge in all 8 audited cases (sign test
  p ≈ 0.008). The post-mortem found the same pattern behind several losses: Muldrotha or Massacre Wurm
  sent into untapped blockers, usually at the lowest-life player. The attack options then showed only
  the defender's life total. Declining an attack Forge wants is a coin flip (5–6), and retargeting an
  attack favours Jev (2–0).
- **Discards:** in all 7 discard overrules in pods 04–06, Jev discarded mana or a tutor to keep a
  mid-size creature: Farseek, Demonic Tutor, Survival, Mind Stone, Sol Ring, Birds of Paradise and
  Pernicious Deed. The options showed only names.

### 3. Plans left unexecuted

When the strategist worked, it was usually right. What failed was getting its plan through the
executor.

- **Gating on a pass Forge couldn't evaluate.** 71% of all offered plays carried the tag "Forge's
  heuristic AI would not do this: CantPlayAi". In main phase 1 that mostly means Forge casts
  permanents after combat (`PermanentAi.checkPhaseRestrictions`). So Forge's default in main 1 was
  usually "pass", and the margin gate protected it.
  - In 55 of 61 turns where main 1 ended in a pass with mana up, Forge's first main-2 default was a
    play, sometimes taking the Muldrotha permission or the mana the memo needed.
  - The worst case was pod03-g2 t49. With 10 mana and a memo naming three removal spells for the
    angels, Jev leaned toward the removal by 0.14 (gate: 0.15). Forge passed, we attacked into the
    angels and lost.
  - The gate is 0.10 now. A blind audit of gated passes alone was a coin flip (27–26), so this is a
    sequencing problem, not proof that Jev should always overrule.
- **Duplicated options.** 21% of action windows listed the same play two or three times. Muldrotha's
  permissions get re-applied to copies. Duplicates split Jev's probability and make the margin harder
  to clear, and 12 logged "overrules" were Jev picking the twin of Forge's own option.
- **Our own upkeep.** Forge fired instants in our upkeep and draw step, and Jev went along. In pods
  04–06 it accepted 10 of 10. Examples:
  - a Capsule activation that made the memo's main-phase Toxic Deluge unaffordable (game-losing);
  - Heroic Intervention with nothing to protect;
  - in pod03-g1, an Assassin's Trophy that tapped the black sources Massacre Wurm needed.

  The big "don't veto Forge's play" margin applied there too.
- **Labels that hide the effect.**
  - Twisted Embrace showed only its Aura host ("→ target: Siren Stormtamer [ours]"), never the
    destroy target. Invasion of Innistrad and Binding the Old Gods showed only their names. Across
    pods 04–06 these three premium answers were offered 86 times and cast once.
  - Some trigger questions had an empty description, e.g. "Our triggered ability from Grist ()". In
    pod04-g3 Jev then aimed Grist's −2 at our own permanent, and that was game-losing. A smoke run
    after the other fixes caught Soul-Guide Lantern doing the same: it exiled our own One Ring from
    our graveyard.
  - Opponents' emblems weren't in the state at all. Sephiroth's drain-on-every-death emblem killed us
    in two games; neither the executor nor the strategist ever saw it.

### 4. Strategy and deck

The strategist's 10 mistakes are threat-ranking errors:
- following a dossier's kill-on-sight list for cards that never appeared;
- spending premium removal on commanders that came straight back (Edgar, Teval, Giada);
- missing the board engine that was actually winning (Y'shtola's Exsanguinate line, Giada's angels,
  Sephiroth's emblem);
- feeding opponents' death triggers with our own removal.

The deck's weakness against this gauntlet: its three *recurring* kill spells all say "nonblack"
(Executioner's Capsule, Seal of Doom, Shriekmaw), and most of the gauntlet is black. Its unrestricted
answers are one-shots or sorcery-speed sagas, and it has few answers to indestructible or recurring
fliers. That is a deck-tuning question and is left for `tune-deck`. The pilot comparison keeps the
list fixed.

## Fixes

| finding | fix | evidence it works |
|---|---|---|
| strategist failure text stored as a memo | `claude_cli.run` raises on failure; the old memo is kept; the report warns | unit test |
| mulligans inverted | land count and hand summary in the question; overruling Forge's mulligan needs the 0.35 margin | offline re-ask: 18 backwards → 0 |
| sacrifice costs never asked | `PilotAi` (Forge's brain, swapped in) routes every single sacrifice cost we pay to the pilot; the dead `PilotCostDecision` is removed | smoke: asked (e.g. Ashnod's Altar, where Jev saved Muldrotha from Forge's pick) |
| discard costs never asked (Survival) | same route via `getCardsToDiscard` | compiles; not yet seen in a game |
| optional sacrifices (Braids) picked by Forge | asked, with "choose nothing" | smoke: asked |
| shock payment silent | life-only "pay or else" costs are asked (with our life and untapped mana); fetch options say "enters tapped", "untapped only if we pay 2 life" or "enters untapped"; guidance keeps the life below about 10 | smoke: asked; Jev paid every time, including at 4 life before the guidance |
| Ghostform fizzles | decline the command-zone move while one of our return-to-battlefield triggers is pending | smoke: Muldrotha stayed in the graveyard and Ghostform returned her |
| X chosen by Forge | X questions (earlier commit) | earlier smoke runs |
| "up to one target" triggers never asked (Galactus chapter I) | asked, with a "no target" option | smoke: asked; Jev took Zodiark over Forge's Sauron |
| blank trigger descriptions | fall back to the trigger's own text, then the card's | smoke run 3 |
| targets aimed at our own cards | overruling Forge to aim a trigger or spell at our own card when Forge aims at an opponent's needs the 0.35 margin: Grist's −2 in pod04-g3; Soul-Guide Lantern exiled our own One Ring in two smoke runs even with its text shown | unit test |
| CantPlayAi label misread as judgement | "Forge's AI would wait and cast this after combat" when that is the reason | smoke |
| duplicated options | deduplicated by label | smoke |
| Muldrotha permissions invisible | options name the permission they use; the state lists which are open this turn | smoke |
| Forge's upkeep spending | in our own upkeep and draw step with an empty stack, Forge's play is no longer the default; the window says mana spent now is gone for the main phase | smoke: Jev still takes the good upkeep plays confidently (Capsule and Bauble cracked in upkeep so Muldrotha can recast them that turn, p 0.5–0.9) |
| main 1 and main 2 look identical | windows say "before combat" or "after combat; no more combat this turn" | compiles |
| Forge's blocker missing from block options | block candidates computed with Forge's blocks lifted; the question gives total incoming damage against our life | compiles |
| attack overrules into blockers | sending an attacker Forge keeps home needs the 0.35 margin; guidance protects the commander and engine pieces; options carry Forge's combat outlook (earlier commit) | blind audits 8–0 |
| discard overrules | options give type, mana value, "makes mana", and permanent vs instant/sorcery; overrules need the 0.35 margin | pods 04–06: 7 of 7 wrong |
| emblems invisible | opponents' command-zone effects are in the state, card text and the strategist's facts | compiles |
| stolen cards read as theirs | labels say "owned by us" | compiles |
| plans not matched to options | options the memo's THIS TURN or HOLD line names are tagged | offline A/B, below: moves Jev onto the plan; a blind judge is split 28–24 |
| sacrifice outlets activated for nothing | found only after the sacrifice-cost hook existed: Jev activated Claws of Gix ("sacrifice a permanent: gain 1 life") up to four times a turn and paid with lands and mana rocks. The pick question now offers "cancel the activation" (Forge decides every cost part before paying any, so nothing is spent), a cancelled activation isn't offered again that turn, and the action guidance says a sacrifice cost costs a card | smoke runs 3–4 |
| threat ranking | strategist checklist: judge threats from the board and emblems, count death triggers our removal feeds, and remember that killing a commander buys a turn or two | none yet |

### Offline A/B: tagging the planned plays

`research/plan_marker_ab.py` re-asked Jev all 804 action decisions from the arm that had a real memo
and at least one option the memo names. Each decision was asked once as logged and once with the tags.

| | Jev's pick is a planned play | final answer is a planned play | final answer is pass |
|---|---|---|---|
| as logged | 527 | 520 | 236 |
| with tags | 565 | 572 | 202 |

The final answer changed in 93 decisions:
- 53 moved from an unplanned answer to a planned play;
- 1 moved the other way;
- 37 swapped one planned play for another;
- 2 swapped one unplanned answer for another.

Moving toward the plan is only good if the plan is good. A blind judge (Opus 5.5, memo hidden) compared
Jev's pick with and without the tags on the 53 decisions that moved toward the plan:
- plan-following pick better: 28
- untagged pick better: 24
- unparsed: 1
- sign test p = 0.68

**That's a coin flip.** Either reading fits:
- The plan's value lies in sequencing across decisions, which a judge seeing one decision without the
  memo can't credit.
- The memos aren't reliably better than Jev's own reading, decision by decision.

The tags stay in because the architecture is meant to execute the plan and they cost nothing. The
decision log records which options were tagged, so the next arm can test them at game level. This is
not evidence that they help.

## What this does and doesn't show

- The mistakes are real and mostly mechanical, and each fix above addresses a mechanism seen in the
  logs. Most are verified only mechanically: the question is now asked, or the label now reads right.
- **None has game-level evidence yet.** The one arm that tested the v3 strategist was half
  contaminated, and 24 games can't separate a 10-point difference anyway.
- The next step is a clean arm with every fix, run on its own: no concurrent Claude experiments. It
  should be compared against Forge's AI on the same pods. About 96 games per arm resolves a 10-point
  difference at the usual confidence. With the strategist that is 8–10 hours, or 2–3 hours with Jev and
  a static plan.
