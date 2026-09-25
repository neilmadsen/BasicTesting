# Threat order: the strategist decides who matters, the executor follows

Follow-up to [the fast-loop note](2026-09-24-fast-loop.md). A loss anatomy of the recent arms
(`research/loss_anatomy.py`, from pod logs) showed:

- We keep pace on mana and cards: we match the table's land drops and cast 3–4 more spells a game than
  the average opponent.
- We aren't focused: we take 22–29% of the damage players deal to players.
- We die to the runaway player. In 69–91% of our combat deaths, the main attacker went on to win.

It also showed the executor pointing damage *away* from the eventual winner, compared with Forge's own
defaults on the same decisions.

A board-power "leader score" would misread combo and control decks. It would also be overfit to Forge,
whose AI plays those decks badly. So the judgement stays with the strategist, and code only supplies
evidence and carries the decision to the executor.

## What changed

- **THREAT ORDER.** A new memo line where the strategist ranks the opponents ("P3 > P1 > P2"), with
  why (board, combo, control, drain, commander damage) and our stance toward each.
- **OPPONENT STANDING.** A new block in the strategist's prompt with per-opponent facts: creatures and
  power, and whom that kills unblocked; lands untapped; hand, graveyard and library; emblems; recent
  casts. It is framed as evidence, not a ranking.
- **Tags.** Attack and target options are tagged with the memo's rank for the player they hit. Attack
  options also say when our unblockable attackers are lethal on a player. This came after the first
  wording turned 16 attacks into holds on replay, including a lethal one.
- **Scorecard.** It now reports the share of our attacks and removal aimed at the memo's #1 threat, next
  to Forge's default on the same decisions.
- **Per-game seeding.** Forge-only baselines now run through the same launcher as piloted arms, every
  game is reseeded, and every game starts a fresh match.

## Results

### Transmission works

In the 48-game Opus arm (strategist every 3rd turn), every memo had a THREAT ORDER line:

| aimed at the memo's #1 threat | ours | Forge's default, same decisions |
|---|---|---|
| attacks, before (K=3 arms) | 0.37–0.49 | 0.57–0.63 |
| attacks, now | **0.87** | 0.67 |
| removal, now | **0.89** | 0.66 |

### The strategist makes its own calls

- In 64 of 183 memos (35%), its #1 threat was not the biggest board. The reasons it gave: drain
  engines (24), combo (20), ramp engines (16), control (6).
- In those disagreements, its pick and the biggest board each went on to win 20 times.
- "Went on to win" is biased against it. Forge plays combo badly, and we attack whoever it names.

### Game level (48 games each, same pods)

| | avg finishing place | 1st/2nd/3rd/4th |
|---|---|---|
| Forge AI (old seeding) | 2.60 | 8/14/11/12 |
| Jev + static plan (old seeding) | 2.92 | 6/7/20/15 |
| Jev + Opus every 3rd turn + threat order (old seeding) | 2.70 | 7/14/12/14 |
| Forge AI (per-game seeding) | 2.52 | 7/19/12/10 |
| Jev + static plan (per-game seeding) | 2.98 | 2/12/19/15 |

**Jev with a static plan is worse than Forge's AI.** With per-game seeding the pair differs by +0.46
places, paired standard error 0.19, about 2.4 standard errors. The old-seeding pair agrees (+0.32). This
overturns the 24-game result in the fast-loop note, where the static arm placed 2.42; that was a lucky
sample.

**With the Opus strategist and the threat order, the pilot is level with Forge** (2.70 against 2.60).
It is about 0.2–0.3 places better than the static plan, but that comparison is not paired.

### Per-game seeding: reproducible, not less noisy

- Two Forge-only runs of the same seeds now replay mostly identically: games 2 and 3 to the end, and
  game 1 for 37 of 58 turns. Before, every game after the first diverged at once.
- It does not reduce noise in pilot-versus-Forge comparisons. Paired games stay identical for a median
  of 4 turns, until the first differing decision, and after that the four-player game decorrelates
  completely: place correlation −0.04, paired standard error equal to the unpaired one.
- It remains useful for reproducing and debugging specific games, and for counterfactual reruns of
  early-game decisions.

## What this means

- **The static-plan loop is not a neutral test bed.** Without the strategist, the executor loses about
  0.4–0.5 places to Forge's AI. With it, the pilot only gets back to parity. So the executor, left to
  itself, still gives away value somewhere, even though blind audits of its overrules keep favouring it
  (actions 44–13, non-actions 48–23).
- **Where the value leaks is the open question.** The per-decision audits and the games disagree; the
  audits can't see tempo or interactions. The direct test is an ablation: let Jev decide only one kind
  of decision (actions, or combat, or targets and costs) and leave the rest to Forge. Then compare
  finishing place against Forge on the same seeds. These are static-plan arms, about 25 minutes each
  with no Claude calls. At 48 games each they can resolve differences of about 0.4 places.
