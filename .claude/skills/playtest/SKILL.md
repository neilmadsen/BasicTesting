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
permissions. The pilot sits on our seat only and re-decides almost everything
Forge's AI would decide there. Every hook computes Forge's own answer first,
asks the pilot to confirm or change it, checks the result with Forge's rules
validators, and falls back to Forge's answer if anything is off.

| kind | what Jev decides |
|---|---|
| `action` | what to do with priority: in our main phases, in response to an opponent's spell or ability, at the end of an opponent's turn, and at any other point where Forge wants to act. Options are Forge's pick, plays Forge approves, lands, and legal, payable plays Forge *declines* (labelled with its reason). |
| `tgt_*` | the target for every targeted option, asked speculatively in the same call |
| `attack` | per creature: hold, or which player or planeswalker to attack |
| `block` | per attacker coming at us: no block, or which creature blocks it |
| `mulligan` | keep or mulligan |
| `confirm` | "you may" prompts (optional costs, may-triggers), and "pay N life or ..." (shock lands) |
| `choose` | single-entity choices made by effects |
| `optional-trigger` | whether to use a "you may" trigger |
| `search` | which card a tutor, fetch land, ramp spell or "return a card" effect takes (one option per distinct name, with type line and text) |
| `discard`, `discard-cost` | which card to discard, for effects, cleanup and costs (Survival of the Fittest); options give type, mana value and whether it makes mana |
| `sacrifice`, `sacrifice-cost` | which permanent to sacrifice: for effects (including optional ones like Braids'), and for costs such as a sac outlet's |
| `scry`, `surveil` | per card: keep on top, or bottom/graveyard |
| `trigger-target` | targets for our triggered abilities (ETB removal, Hostage Taker, "up to one target" saga chapters) |
| `x_*` | X for the chosen play (mana X, or e.g. "pay X life"), asked speculatively with the action |
| `hold` | in our main phases: keep specific mana open until our next turn for one instant-speed play (enforced through Forge's own mana reservation) |

- **Executor (Jev):** one call per decision point, one Choice question per
  sub-decision. Its state is the deck plan (brief.md plus the pilot notes), the
  latest strategy memo, the board, oracle text for every non-land card on it
  (plus our hand and the stack), per-kind guidance, and what has changed since
  the memo was written. Option text carries P/T, damage, loyalty and controller
  for targets, and type lines for searched cards. Without type lines, Jev fetched
  basic Swamps over Zagoth Triome: *what the options say is most of the pilot's
  skill*. It overrules Forge only when its top choice beats
  Forge's by a probability margin (`EDH_PILOT_GATE`, default 0.10; an audit of
  sub-margin preferences found them worse than Forge below a 0.10 lead and better
  above it).
- **Strategist (optional, `--strategist claude-cli`):** Opus 5.5 plans once per
  turn of ours (and on escalation). v3 is the default (`--strategist-version`).
  It sees:
  - our deck by zone, with the builder's role notes (the library is what's left
    to tutor);
  - full oracle text with costs;
  - a scouting dossier per opposing commander (`gauntlet/dossiers/`): plan,
    kill-on-sight, what our plays feed, and an EDHREC interaction profile;
  - mana counted from oracle text;
  - commander tax, stolen permanents, emblems and recent casts;
  - OPPONENT STANDING: per-opponent facts (creatures and power, and whom that
    kills unblocked; lands untapped; hand; graveyard; recent casts), given as
    evidence, not a ranking;
  - the opponents' triggers our own plays feed (Blood Artist, Grave Pact...).

  The memo has seven lines: THIS TURN / TARGET / WIN PATH / THREAT ORDER /
  THREATS & ANSWERS / HOLD / REPLAN IF. THREAT ORDER is the strategist's
  ranking of the opponents ("P3 > P1 > P2", with why and our stance); it is its
  call, not a formula, so a combo or control player can outrank the biggest
  board. Attack and target options are tagged with it, and attack options also
  say when our unblockable attackers are lethal on a player. A verify pass (`--strategist-verify low`, the default)
  audits each memo's mana, rules and targeting before the executor sees it.
  That takes about 40–70 s per memo. Planning every turn makes a piloted game
  15–20 minutes; `--strategist-every 3` plans every third turn of ours (and on
  escalation), with a NEXT TURNS line that carries the executor between plans,
  for about a third of the calls. Use it for executor work. Use `--clock 2700`. `--async-strategist` doesn't pause the
  game, but the memos then lag. Build a missing dossier with
  `python3 -m edhkit.dossier <bracket>`.
- **Escalation:** the sidecar diffs the board against the one the memo was
  written on. It checks for lost opponents, life swings of 8 or more, board wipes
  (our or an opponent's), big creature swings, named permanents of ours that
  died, and our commander leaving. Every Jev call also answers "does this change
  invalidate the memo?". A confident yes (`EDH_PILOT_ESCALATE`, default 0.6)
  makes the strategist re-plan *mid-turn*, and the decision is re-asked under the
  new memo. The cap is one per turn and 8 per game.
- **Logs:** `sims/<stamp>/pilot_decisions.jsonl` records every decision (kind,
  questions, options, choice, probabilities, whether it overruled Forge), every
  memo and every escalation, with the board changes that triggered it. Read them
  to see *how* the deck was played, not just whether it won. The report line
  shows questions and overrules by kind. `HOOK ERRORS` means a hook threw and
  Forge's answer was used instead; fix it before trusting the run.

**What it's for:** making the sim play the deck the way its brief says. The
pilot is only on our seat, so compare *arms* (same pods and seeds, Forge vs
pilot) and *decks under the same pilot*. Don't compare a piloted win rate with
Forge-vs-Forge numbers as if they meant the same thing.

**What the evidence says so far** (`research/2026-09-23-jev-pilot-v2.md`, Muldrotha, B3):
- A blind judge prefers the pilot's overrules about 2 to 1 (p = 0.0015). With
  Opus memos, the pilot plays the whole deck and casts the commander earlier.
- It has not yet won more games than Forge's AI (4/24 against 5/24 in the best
  arm), and attacks are its weakest decision kind.
- Without the strategist, Jev barely executes an engine plan.

So use the pilot to see a deck *played as designed*: which cards get used, how
the engine runs, and memos you can read as a how-to-pilot guide. Keep Forge-only
sims as the A/B baseline for deck versions. Never quote a piloted win rate as a
deck's strength.

**Checking the strategist.** `edhkit/memo_lab.py` pairs logged memos with their
boards. It can have an expert reviewer score them on a top-player rubric,
separating reasoning failures from information gaps, and it can compare two
strategist setups blind on the same boards. That's how v3 was built:
`research/2026-09-23-strategist-memos.md`.

**Why games are lost.** `research/2026-09-24-postmortem.md` traced every reviewed mistake of a 24-game
arm to the decision that caused it; `research/game_digest.py` (turn-by-turn digests for reviewers) and
`research/decisions_at.py <log> <game> <turn>` (every option, Forge's default, Jev's pick) are the tools.
Most losses were execution: resource choices Forge made unasked, and Jev overrules in the three kinds
where they are reliably wrong (mulligans, attacks Forge wouldn't make, discards), which now need the
0.35 margin. Action options the memo's THIS TURN or HOLD line names are tagged for Jev.

**Execution scorecard.** `./edh scorecard <sim-out> [...]` counts, per game and from the logs alone, the
mistake classes the post-mortem found: planned plays taken (fresh vs older memo), turns ended with mana
and a castable play, lands paid to sacrifice costs, cancelled activations, attacks where a blocker can
kill ours, chump blocks, keeps of 0–1-landers, self-aimed targets, X left to Forge, shock payments, and
overrule/gate rates by kind, the share of our attacks and removal aimed at the memo's #1 threat
(against Forge's default on the same decisions); and, from the pod logs (so Forge-only baselines too), finishing place
(1 = won … 4 = first out, far less noisy than win/loss) and pressure: attackers sent, combat damage dealt,
life the opponents lost, damage taken. Compare a pilot arm with a Forge-only run on the same pods
(same `--games`, `--seed` and `--per-pod`, which decide the pods). It is the fast readout for executor
changes; win rate is the slow one. Per-decision blind audits can't see tempo: in the first K=3 arm the
judge liked most overrules while the pilot sent 1.9 attackers a game to Forge's 5.0 and finished last
more often. Read the pressure lines before believing an audit.

**Replay.** `./edh replay <sim-out> --deck deck.txt` re-asks every logged decision of a `--log-state` run
under the executor as it is now (same board, memo and options; Jev calls only, well under a minute for a
few hundred decisions) and reports which answers change, by kind. `--judge N` has a blind Opus judge
compare old and new answers on N changed decisions. Use it for changes to guidance, margins, plan tags
or memo handling; changes to the Java side (which options exist, their labels) need new games.

**Checking the pilot itself.** Add `--log-state` to a piloted sim, then run
`./edh pilot-audit <sim-out> --deck deck.txt --n 120 --hide-memo`. A blind Opus
judge compares the pilot's overrules with Forge's picks on identical boards.
It takes about 5 minutes and no extra games, and it gives far more statistical
power than win rates. Read the cases it scores for Forge: that's how the
fetch-land veto bug and the stranded-commander bug were found. Check the
report's `HOOK ERRORS` / `loop-breaker` counts too.

Attack and block options carry Forge's own combat evaluation (how many untapped
creatures can block it and would kill it; whether our blocker kills the attacker
and survives). `./edh sim --pilot count` runs Forge on our seat with every
decision tallied, to see what the pilot never decides
(`research/2026-09-23-pilot-control-surface.md`).

**Limits:** Forge still pays mana (apart from holds and life-only "pay or else" costs), orders triggers, picks modes for modal
spells (its AI picks modes and their targets together), and makes multi-target
and multi-select choices. Multi-blocks survive only where Jev agrees with
Forge's primary blocker. The opponents are still Forge's AI, which misplays
politics and combo. A piloted game takes minutes rather than seconds, and more
when the strategist is on. Full LLM-vs-LLM play would be slower still, and
LLMs track board state worse than they plan.
