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
- Respect **The user's taste** (CLAUDE.md): control and creativity, not one-note.
  Unless the commander truly can't support it, one build is genuinely interactive
  (counters, removal, theft, table politics), and one takes a creative line the
  crowd misses. Within each build, look for a second win path and a midgame that
  has decisions in it.
- Before picking archetypes, browse the pool for the commander's core mechanic
  yourself, e.g. `./edh pool --commander "<cmdr>" --regex '<its mechanic>' --unlisted`.
  You only need a page or two, but archetypes nobody builds usually start from a
  card nobody plays.
- Record the rejected archetypes and why. The user will want to know.

## 4. Write a brief per archetype → `decks/<slug>/<arch>/brief.md`

The brief steers the builder, and `jev rank` also sends it as the state for scoring.
Keep it focused (Jev's accuracy drops with irrelevant detail), under 1500 words:

````markdown
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

```engine
name: <what the deck must assemble>
by: <turn>
commander
<N> of: <card>; <card>; regex:<rules-text pattern>; tag:<role>; type:<type word>
held <N> of: <cards to keep in hand, e.g. tag:counterspell>
tutors: <cards that fetch a missing piece>
```
````
The engine block is the deck's thesis written as a test: `./edh engine` measures how
often it comes together by the stated turn. Write one block per package that
matters (e.g. the engine, and the interaction shell). Keep it honest. A spec that
any deck meets tests nothing.

## 5. Build in parallel (subagents)

Spawn one **`deck-builder`** subagent per archetype, all in a single message so
they run concurrently. Give each the brief path, commander, bracket, output folder,
and a sim budget (default `--games 16`, a smoke test). They scout (including
browsing the pool by mechanic), build, validate, tune the mana and the engine,
audit (omissions, claims, gems), smoke-test, and write `deck.txt`, `notes.md` and
`proxies.txt`. The agent definition may have changed since the session started, so
tell each builder to read `.claude/agents/deck-builder.md` and follow its procedure. Their Forge sims
share a cross-process slot lock, so running several at once is safe (just slower).

While they run: nothing is required of you. If Forge is still building, check it.

## 6. Review the audits (you)

Read each deck's `audit/*.json` and the builder's summary. You are the quality bar:
- an engine online-by rate below the builder's own target;
- unresolved `wrong` claims;
- gems the judge rejected that have no defence;
- staples omitted without a reason.

Any of these goes back to the builder before the critic sees the deck.

## 7. Critique (subagents)

When the builders are done, spawn one **`deck-critic`** per deck (in parallel).
The critic reads the deck cold and reports what an experienced player at that
bracket would object to: dead slots, weak gems, missing interaction, mana issues,
bracket smell. Send each critique back to its builder (SendMessage to the same
agent, so its context survives) to revise. If you can't message the builder, make
the edits yourself. Revisions must re-run `validate` and `analyze`. Re-sim only if
the change is structural.

## 8. Confirm with the pilot (optional, small)

The Jev pilot plays the deck as designed: it casts the cards Forge's AI won't. Run
2–4 piloted games per deck with a sparse strategist:

`./edh sim deck.txt --bracket N --games 4 --pilot jev --strategist claude-cli --strategist-every 3 --log-state --clock 2700`

Then run `./edh bugscan <out>`. This checks *mechanisms* (does the engine assemble
in play, do the gems get cast and do what the notes claim), not strength: four
games rank nothing. One run like this costs about 40 Opus calls per deck, so mind
the spend limit and run the decks one after another, not in parallel. If a
mechanism fails, fix the deck or its pilot notes and say so in notes.md.

## 9. Compare and deliver → `decks/<slug>/README.md`

Write the deliverable for the user:

1. **One-paragraph verdict.** Which build you'd hand them and why, and who would
   prefer each of the others.
2. **Comparison table.** Rows:
   - plan, and its win paths;
   - goldfish commander turn;
   - engine online-by rate at its turn;
   - interaction count;
   - resilience;
   - complexity to pilot;
   - claims fixed and gem hit rate;
   - Forge smoke test (with its CI, and never-cast count);
   - pilot confirmation result, if run;
   - Game Changers used.
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
- [ ] Every brief has an engine block; the engine report is in notes with the rate the builder accepted
- [ ] `audit claims` has no unresolved `wrong`; `audit omissions` has no unanswered `!!`; every gem names its staple
- [ ] At least one build is interactive and one is creative (CLAUDE.md, The user's taste), or README says why not
- [ ] Smoke sim ran (or you say why not), and never-cast cards were each reviewed
