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

## About LLM-vs-LLM play
It's possible in principle (two agents alternating over a rules engine), but
slower and more expensive than Forge per game, and LLMs track board state worse
than they reason about strategy. Better use of an LLM: read Forge logs and sample
hands and critique the *decisions the deck asks of its pilot*. The `deck-critic`
subagent does that.
