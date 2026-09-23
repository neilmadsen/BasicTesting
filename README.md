# Commander deck lab

An agentic Commander deckbuilder that runs inside Claude Code. Give it a commander
and a bracket, and it maps the strategy space, builds a deck for each distinct
archetype worth building, checks the bracket rules, playtests with a mana
simulator and Forge AI pods, and hands back annotated, proxy-ready lists.

```
/brew Muldrotha, the Gravetide bracket 3
```

## How it works

```
             ┌─ strategy map (you ↔ Claude; one round of questions at most)
commander ──►│
 + bracket   └─ per archetype, in parallel subagents:
                  scout ──► build ──► validate ──► goldfish ──► Forge sims ──► revise
                    │                                                      ▲
                    │   Jev: score every legal card vs the strategy brief  │
                    │   Scryfall syntax · Tagger roles · EDHREC baseline   │
                    └───────────── deck-critic subagent ───────────────────┘
                                          ▼
                     decks/<commander>/README.md + deck.txt + proxies.txt
```

- **Card data**: Scryfall's Oracle bulk file (one download, ~35k cards) goes into
  SQLite with full-text search, plus ~50 functional role tags from Scryfall
  Tagger (ramp, board-wipe, sacrifice-outlet…).
- **Search**: three layers, precise to fuzzy. Scryfall syntax (`./edh scry`),
  offline filters (`./edh search`), and **Jev**, TypeSafe's calibrated decision
  model, which scores *every* legal card in the color identity against a written
  strategy brief. A full pass over a three-color pool (~17.5k cards) takes about 30 seconds and
  costs about $0.22, which is what makes exhaustive hidden-gem hunting practical. EDHREC inclusion rates mark which strong fits are
  under-played.
- **Rules**: legality plus Commander Brackets (Feb 2026 update: 53 Game Changers),
  with combos, mass land denial and extra turns detected through Commander Spellbook.
- **Testing**:
  - *Goldfish*: a Monte Carlo mana simulator, 20k trials in seconds. It tunes land
    count, ramp and colors, and measures when the commander comes down.
  - *Forge*: the open-source rules engine (~34k cards implemented), running
    headless 4-player AI pods against a gauntlet of EDHREC average decks for the
    same bracket. It reports win rate with a confidence interval, game length,
    commander timing, per-card cast rates, and which cards the AI can't play.
- **Output**: an annotated `deck.txt` (every card has a role and a reason), `notes.md`
  (plan, gems, test results), `proxies.txt`, and an optional print-ready PDF.

## Setup

Requirements: Python 3.10+, and for simulations git + JDK 17+ + Maven.

```bash
./edh setup                 # card DB + role tags (~3 min)
./edh forge setup           # optional: clone + build Forge for sims (~10 min, ~1 GB)
cp .env.example .env        # add TYPESAFE_API_KEY for Jev (optional but recommended)
./edh doctor
```

Opponent gauntlets for all five brackets are checked in under `gauntlet/`.
Rebuild them with `./edh gauntlet build --bracket N`.

## Using it

Open Claude Code in this directory and ask for a deck. `CLAUDE.md` and the skills
in `.claude/skills/` hold the method; `.claude/agents/` defines the `deck-builder`,
`deck-critic` and `card-scout` subagents. The CLI works on its own too:

```bash
./edh card "Muldrotha, the Gravetide"
./edh edhrec "Muldrotha, the Gravetide" --bracket 3
./edh jev rank --brief decks/muldrotha/lands/brief.md --ci "Muldrotha, the Gravetide" --commander "Muldrotha, the Gravetide"
./edh scry 'o:"from your graveyard" t:land' --ci BUG
./edh validate decks/muldrotha/lands/deck.txt --bracket 3
./edh analyze decks/muldrotha/lands/deck.txt
./edh sim decks/muldrotha/lands/deck.txt --bracket 3 --games 40
./edh export decks/muldrotha/lands/deck.txt --format pdf
```

## What the simulations can and can't tell you

Forge's AI is a solid goldfisher with blockers. It is weak at combo, control,
stax, and anything political, and some cards are flagged as unplayable for it (the
sim report lists them). Forty 4-player games take about 12 minutes on 4 cores
and carry a ±13-point confidence interval on win rate. That's enough to catch a
deck that doesn't function or a big structural difference. It isn't enough to rank
single-card swaps, and the tooling refuses to pretend otherwise. The goldfish is
where fine tuning happens.

## Layout

```
edh                 CLI entry (bash shim → python -m edhkit)
edhkit/             cards, tags, search, jev, edhrec, deck, analyze, brackets, forge, gauntlet, export
.claude/skills/     brew · card-scout · deck-construction · playtest · brackets · tune-deck · proxy-export
.claude/agents/     deck-builder · deck-critic · card-scout
gauntlet/b1..b5/    opponent decks per bracket (Forge .dck)
decks/              output
tests/              python3 -m unittest discover tests
```
