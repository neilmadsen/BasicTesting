# Strategist model A/B: Opus 5.5 vs Haiku 5.5 (offline, paired, blind)

**Question.** Does writing the per-turn strategy memo with Haiku 5.5 instead of Opus 5.5 change plan quality materially?

**Answer.** Yes. At the production effort (medium), Haiku is clearly worse. Haiku at high effort closes part of the gap but still trails. Its memos carry roughly two to five times as many play-changing errors. The errors are the kind the executor follows faithfully: misreading ward, equipping a shrouded creature, missing a live lethal, giving the wrong player the Treasures. Per memo, Haiku is about 5–8× cheaper, not 40×, because it thinks 4–8× longer, and in wall-clock terms it is *slower* than Opus.

## Design

- **Boards.** 36 logged decision-time states from three clean Opus rounds (`vivi-opus10j`, `l`, `m`; no strategist failures). They are stratified 9 each into early, mid, late and escalation re-plans (`memo_lab.sample_points`, seed 5). Each board is paired with the previous memo Opus actually wrote, so both arms get the same continuity.
- **Arms.** Each arm runs the exact production path: `strategist.prompt` + `system_for(1)` draft, then the verify pass at low effort *by the same model*.
  - Opus 5.5 at medium effort (production)
  - Haiku 5.5 at medium effort
  - Haiku 5.5 at high effort
- **Judges.** Judging is blind and pairwise, with A/B order randomised per board (seed 11). The judge sees the strategist's full prompt and returns:
  - a verdict and margin;
  - each memo's errors, graded minor or major (major = loses a card, mana, tempo or the game, or is illegal);
  - whether following one memo rather than the other would change play this turn cycle.

  Opus 5.5 (high effort) judged everything. Sonnet 5.5 (high effort) judged the same pairs as a check on self-preference.
- **Script and data.** `research/strategist_model_ab.py` (gen / judge stages, cached), `strategist_model_ab_summary.py`, and data in `2026-10-08-strategist-model-ab-data/`.

## Results

| Comparison | Judge | Opus wins | Haiku wins | Same | Opus share of decided | Sign test p |
|---|---|---|---|---|---|---|
| Opus vs Haiku-medium | Opus | 33 | 3 | 0 | 0.92 | <0.001 |
| Opus vs Haiku-medium | Sonnet | 28 | 8 | 0 | 0.78 | 0.001 |
| Opus vs Haiku-high | Opus | 30 | 4 | 2 | 0.88 | <0.001 |
| Opus vs Haiku-high | Sonnet | 20 | 9 | 6 | 0.69 | 0.06 |

Memos with at least one **major** error, out of 36:

| | Opus judge | Sonnet judge | Both judges flag | Either judge flags |
|---|---|---|---|---|
| Opus (vs Haiku-medium run) | 1 | 4 | 0 | 5 |
| Haiku-medium | 21 | 17 | 13 | 25 |
| Opus (vs Haiku-high run) | 5 | 6 | 3 | 8 |
| Haiku-high | 14 | 11 | 10 | 15 |

On 16 of the 36 Haiku-medium boards, both judges preferred Opus *and* said play would differ. Against Haiku-high the figure is 12.

**Cost and latency (one representative prompt, about 12K tokens cached input).**

| Arm | Cost per call | Output tokens | Speed |
|---|---|---|---|
| Opus-medium | $0.033 | 1.5K | 17 s |
| Haiku-medium | $0.0043 | 6.3K | 31 s |
| Haiku-high | $0.0070 | 11.5K | 52 s |

Over the 36-board run, median draft + verify wall time was 64 s for Opus, 110 s for Haiku-medium and 145 s for Haiku-high.

## What Haiku gets wrong

The major errors cluster into rules and card-text mistakes, plus tactical blind spots on complex boards. Rarely is the problem a bad strategic read:

- **Ward:** it says the opponent pays the ward cost (boards 15, 32). It is the caster, so following the memo loses Rift or Vivi.
- **Shroud:** it says to equip Wizard's Staff to a Vivi wearing Lightning Greaves (27).
- **An Offer You Can't Refuse:** it says we get the Treasures (20).
- **Tagging Vivi:** it treats her {0} mana ability as tapping her and skips a 9-damage attack (7).
- **Hullbreaker Horror:** it misses the lethal loop (21) and wastes the Damper triggers before Blasphemous Act (14).
- **Missed lethal:** with Crackle at X=2 (19), and with an overloaded Rift into an empty board (34).
- **Mana:** it adds commander tax where none exists (35) and writes impossible mana plans (4).

Opus's own major errors were fewer but real. On board 7 it got Crackle with Power's cost wrong ({X}{X}{X}, not {X}), so it claimed a table kill that does not exist. On board 26 it held Chaos Warp when clearing the blocker would have taken a player to 6. Haiku's genuine wins (boards 25, 26, 29, 30) are tactical cleanups where Opus made one such slip.

## Caveats

- **Judge bias.** The Opus judge favours Opus more than Sonnet does (0.88–0.92 vs 0.69–0.78). Some of that is probably self-preference. Even so, the less involved judge still prefers Opus at medium effort with p = 0.001, and both judges agree on the error asymmetry. The Haiku-high result is the one that self-preference could be inflating; under Sonnet alone it is suggestive, not conclusive.
- **Live play could differ in both directions.** Offline, each memo starts from Opus's previous memo. In live play Haiku would build on its own earlier memos, so errors could compound. Equally, the executor's gates and Jev's own scoring catch some memo errors.
- **Plan quality is not win rate.** This measures memo quality, not game outcome. A 10-game Forge arm has about ±0.4 places of noise and would not resolve a difference this size reliably. The offline test is the more sensitive instrument here.
- **Scope.** The sample is 36 boards from one deck (Vivi, a spell-dense, rules-heavy deck). A simpler creature deck might narrow the gap.

## Recommendation

Keep Opus as the strategist. The saving is real but small in absolute terms. At about 13 memos per game, a draft plus verify costs roughly $0.05 with Opus, so Haiku saves on the order of $0.50 per game, but the errors Haiku adds are the very class the bug loop spent rounds 1–11 removing from the executor, re-entering through the plan instead.

If cost matters, the defensible experiments are different. Haiku at high effort only for the verify pass, behind an Opus draft, is the one place where cheap, careful checking fits. Sparse Opus planning (`--strategist-every 3`) roughly thirds the calls without changing the planner.
