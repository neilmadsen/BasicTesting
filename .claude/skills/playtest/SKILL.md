---
name: playtest
description: Test Commander decks with the goldfish mana simulator and Forge AI-vs-AI pods, read game logs, and iterate on swaps without fooling yourself with noise. Use after a deck passes validation, when comparing versions, or when the user asks how a deck performs.
---

# Playtesting

Two instruments, with very different strengths:

| | Goldfish (`./edh analyze`, `./edh goldfish`) | Forge (`./edh sim`, `./edh compare`) |
|---|---|---|
| Measures | land drops, mana by turn, commander timing, color screw, role access | wins vs a bracket gauntlet, game length, what got cast, how we died |
| Noise | tiny (10–20k trials, seconds) | large (40 games ≈ ±13 pts on win rate, ~12 min) |
| Blind spots | opponents, card quality, interaction | Forge AI misplays combo, control, stax, politics; it can't use cards flagged `ai_cannot_play` |
| Use it to | tune lands/ramp/curve/colors | smoke-test that the deck functions; catch dead cards; compare *big* changes |

## Loop

1. **Goldfish first.** `./edh analyze deck.txt`. Tune lands, ramp and colors
   until targets are met (see deck-construction). This is cheap, so iterate freely.
2. **Eyeball hands.** `./edh hands deck.txt -n 6`. Would a good player keep
   these? What do they do on turns 1–3?
3. **Sim.** `./edh sim deck.txt --bracket N --games 32` (≈10 min on 3 workers,
   longer if other sims are running). Output lands in `sims/<stamp>/`:
   `summary.json` plus condensed `podNN.log` files.
4. **Read the result critically.**
   - Win rate vs baseline (25% in 4-player pods). Report the CI, not the point.
   - `commander cast in X% of games, first on round R`. If this is much later than
     the goldfish predicts, opponents are interfering or the AI isn't
     prioritizing the commander.
   - `never cast`: sort these into (a) `ai_cannot_play` flagged, where the sim is
     blind, so ignore; (b) situational cards (wipes, counters), where Forge's AI
     rarely finds the moment; (c) genuinely clunky cards, which you should cut.
     Don't cut a card *because* Forge never cast it. Cut it if you agree, after
     reading it again, that it's clunky.
   - `how we lost`: dying to combat on round 6 means too slow or too little
     defense. Decking or poison means something specific.
   - `from our graveyard: N spells + M lands per game` matters for recursion
     commanders. Forge's AI recasts cheap sacrifice-for-effect permanents readily
     (the Muldrotha recurring-removal build averaged 4 graveyard spells a game) but
     under-uses expensive creature recasts (about 1.9 in the creature-value build).
     If the number is far below what a human would do with the commander's
     turns, the sim is blind to the engine. Say so, and lean on reasoning.
5. **Read two or three logs** when something looks off (a loss where the commander
   was never cast, a very long game). Grep first, then read around the hits:
   `grep -n "P2 cast\|Game Outcome" sims/<stamp>/pod03.log | head -80`.
   Which seat is us is in the `# seats:` header line. Delegate full-log reading
   to a subagent if you need more than a few hundred lines.
6. **Compare only big changes.** `./edh compare old.txt new.txt --bracket N
   --games 60` runs both lists through identical pods, seats and seeds. Single-card
   swaps are below what the sim can resolve, so justify those by reasoning and
   goldfish. Use compare for archetype-level or 8+ card changes, land counts, and
   curve reshapes.

## What not to do
- Don't chase a sim win rate. Forge rewards linear creature decks, so a list
  tuned to beat Forge AI drifts toward stompy.
- Don't report "deck A 31% vs deck B 24%" as a ranking when the CIs overlap.
- Don't run hundreds of games to answer a question the goldfish answers in two
  seconds.

## The Jev pilot (experimental): let our seat play the deck as designed

`./edh sim deck.txt --bracket N --pilot jev [--strategist claude-cli]`

Forge's AI plays every deck the same generic way. It skips cards flagged
unplayable for the AI, and it rarely uses a commander's graveyard or engine
permissions. The pilot replaces one decision for our seat only: what to do with
priority in our main phases (cast, activate, play a land, or pass). Combat,
responses, targets and mana payment stay with Forge.

- **Options:** Forge's own pick, every other play Forge's evaluator approves,
  land drops, and legal, payable plays Forge *declines*. Declined plays are
  targeted with Forge's mandatory-mode targeting and labelled with Forge's
  reason. That last group is where engine decks live.
- **Executor (Jev):** one Choice question per decision. Its state is the deck
  plan (brief.md plus the pilot notes), the latest strategy memo and the board.
  It takes about 0.4–0.6 s and roughly $0.005 per game, and overrules Forge only
  when its top choice beats Forge's pick by a probability margin
  (`EDH_PILOT_GATE`, default 0.15).
- **Strategist (optional, once per turn of ours):** an LLM reads the plan and
  the board and writes a 120-word memo (PRIORITIES / THREAT / HOLD) for the
  executor. The default is `claude-cli`, a lightweight headless `claude -p` call
  on Claude Opus 5.5 at about 10 s per memo. The game pauses for it, since a sim
  can. `--async-strategist` doesn't pause, but the memos then lag several turns.
- **Logs:** `sims/<stamp>/pilot_decisions.jsonl` records every decision (options,
  choice, probabilities, whether it overruled Forge) and every memo. Read them
  to see *how* the deck was played, not just whether it won.

**What it's for:** making the sim play the deck the way its brief says. The
pilot is only on our seat, so compare *arms* (same pods and seeds, Forge vs
pilot) and *decks under the same pilot*. Don't compare a piloted win rate with
Forge-vs-Forge numbers as if they meant the same thing.

**Limits:** blocks, attacks and instant-speed responses are still Forge's. A
declined play gets Forge's mandatory targets, which Jev can see and reject but
not change. Full LLM-vs-LLM play, with every decision made by a language model,
would be slower still, and LLMs track board state worse than they plan.
