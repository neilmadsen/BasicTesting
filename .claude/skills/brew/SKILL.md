---
name: brew
description: Build Commander decks end to end from a commander + bracket. Explores the strategy space, builds one deck per genuinely distinct archetype (in parallel subagents), validates brackets, playtests with goldfish + Forge sims, and delivers proxy-ready lists with a comparison. Use for any "build me a deck for X" request.
argument-hint: "<commander name(s)> [bracket 1-5] [any preferences]"
---

# Brew: commander + bracket → tested, proxy-ready decks

You are the head brewer. Your subagents do the heavy lifting in parallel; you own
the strategy thinking, the quality bar, and the final recommendation.

## 0. Preflight (1 minute)

```bash
./edh doctor
```
- Card DB missing → `./edh setup` (≈3 min).
- Forge not built → start `./edh forge setup` **in the background** now. Sims come
  late in the pipeline and the build takes ≈10 minutes.
- No gauntlet for the target bracket → `./edh gauntlet build --bracket N` (seconds).
- No Jev key → note it. Scouting still works through `scry` and reading, but tell the
  user at the end that a key would widen the search.

## 1. Intake

Resolve the commander(s): `./edh card "<name>"`. For partners or backgrounds, check
the pairing is legal. If the user didn't give a bracket, ask for it. That is the
only question you must ask.

Decide whether to ask anything else. Ask **one** round (AskUserQuestion, ≤4
questions, sensible defaults marked) only when the answers would change what you
build. Good reasons to ask:
- The commander supports very different play patterns (combat vs. combo vs.
  control), and the user's taste would pick between them.
- Hard lines the bracket allows but many players dislike: stax, mass land denial
  at B4, infinite combos at B3/B4, extra-turn chains, theft.
- Pet cards or must-includes. Also how many options they want (default: 2–3).

Otherwise don't ask; the user trusts your taste. Write down the assumptions you
made in the final README.

## 2. Study the commander (you, directly)

```bash
./edh card "<commander>"
./edh edhrec "<commander>" --bracket N     # themes, staples, synergy; the crowd baseline
./edh edhrec "<commander>" --cards 100     # all-bracket view for comparison
```
Read the commander's text like a designer: what does it reward, what does it
break, what resource does it convert into what? What do the popular themes miss?
Look for the second-order reading of the card. What stops it working (graveyard
hate, wraths, taxing effects)?

## 3. Map the strategy space → `decks/<slug>/strategies.md`

List 3–6 candidate archetypes. For each, write the thesis in two sentences, the win
condition, the engine, how it fits the bracket, and how distinct it is from the
others. Then pick what to build:

- Build **each** archetype that is genuinely distinct *and* genuinely good at the
  bracket. The usual count is 2–3, and 1 is fine if one plan dominates. More than
  4 is almost never useful.
- At least one build should go somewhere the EDHREC theme list doesn't, *if* such
  a plan is actually viable. Don't invent a weak deck to satisfy this.
- Record the rejected archetypes and why. The user will want to know.

## 4. Write a brief per archetype → `decks/<slug>/<arch>/brief.md`

The brief steers the builder, and `jev rank` also sends it as the state for scoring.
Keep it focused (Jev's accuracy drops with irrelevant detail), under 1500 words:

```markdown
# <Commander> — <Archetype> (Bracket N)
Commander: <name> — <exact oracle text>
Thesis: <how the deck wins and why this commander makes it work>
Win conditions: <concrete: which cards/boards end the game, by roughly which turn>
Engine: <the loop or value engine; which effects are load-bearing>
Wants: <effects that are premium here, including non-obvious ones>
Avoid: <anti-synergies, effects that hurt the plan, bracket-illegal stuff>
Interaction plan: <what to answer and how: spot removal / wipes / counters / protection>
Bracket constraints: <GC budget, combo policy, etc.>
Targets: lands ~N, ramp ~N, draw ~N, removal ~N, wipes ~N, protection ~N (deviate deliberately)
User preferences: <anything from intake>
```

## 5. Build in parallel (subagents)

Spawn one **`deck-builder`** subagent per archetype, all in a single message so
they run concurrently. Give each the brief path, commander, bracket, output folder,
and a sim budget (default `--games 32`). They scout, build, validate, goldfish,
sim, iterate, and write `deck.txt`, `notes.md` and `proxies.txt`. Their Forge sims
share a cross-process slot lock, so running several at once is safe (just slower).

While they run: nothing is required of you. If Forge is still building, check it.

## 6. Critique (subagents)

When the builders are done, spawn one **`deck-critic`** per deck (in parallel).
The critic reads the deck cold and reports what an experienced player at that
bracket would object to: dead slots, weak gems, missing interaction, mana issues,
bracket smell. Send each critique back to its builder (SendMessage to the same
agent, so its context survives) to revise. If you can't message the builder, make
the edits yourself. Revisions must re-run `validate` and `analyze`. Re-sim only if
the change is structural.

## 7. Compare and deliver → `decks/<slug>/README.md`

Write the deliverable for the user:

1. **One-paragraph verdict.** Which build you'd hand them and why, and who would
   prefer each of the others.
2. **Comparison table.** Plan, speed (goldfish commander turn and sim win round),
   interaction count, resilience, complexity to pilot, Forge win rate with its 95%
   CI, Game Changers used.
3. **Per deck.** Link `deck.txt` and `proxies.txt`, the five cards that define it,
   the gems with one line each, and how to pilot it.
4. **Assumptions and open questions.** Intake defaults and any REVIEW items.
5. **How to print.** `./edh export decks/<slug>/<arch>/deck.txt --format pdf` gives
   3×3 sheets at true size, or paste `proxies.txt` into MPCFill or a proxy printer.

Keep the evidence honest: a 40-game sim with the CI overlapping 25% is "no
detectable difference from a typical deck at this bracket", not a ranking.

Finally, summarize for the user in chat: the options, your pick, and where the
files are. Commit the deck folder if the user is working in git.

## Quality bar (check before delivering)
- [ ] `./edh validate --bracket N` PASSES for every deck; REVIEW items answered in notes
- [ ] Exactly 100 cards; every nonland line has a `# role: why` annotation
- [ ] Goldfish: commander castable by its MV+1 in ≥75% of games (unless the plan doesn't need it early); T4 screw ≤ ~12%
- [ ] Each deck has a stated win condition you could explain in one breath
- [ ] Each deck includes non-staple picks, each justified; no novelty filler
- [ ] Sim ran (or you say why not), and never-cast cards were each reviewed
