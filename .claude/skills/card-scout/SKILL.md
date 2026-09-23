---
name: card-scout
description: Find candidate cards for a Commander deck, especially under-played "hidden gems", using Jev semantic screening over the full legal pool, Scryfall-syntax search, role tags, and EDHREC as the popularity baseline. Use when building a deck, filling a role, or when asked "what cards do X / what am I missing".
---

# Card scouting

The problem with manual deckbuilding is coverage, not intelligence. Nobody can
read 12,000 legal cards against a plan, so everyone converges on the same 150.
This skill does the coverage pass mechanically and saves your judgement for the
shortlist.

## The funnel

1. **Baseline: what everyone plays.** `./edh edhrec "<commander>" --cards 120`.
   Note the staples, the high-synergy cards, and the themes. Staples are your
   comparison point: a gem has to beat the staple it would replace.

2. **Exhaustive semantic screen (Jev).** Score every nonland card in the color
   identity against the archetype brief:
   ```bash
   ./edh jev rank --brief decks/<slug>/<arch>/brief.md --ci "<commander>" \
       --commander "<commander>" --top 300 --out decks/<slug>/<arch>/candidates/rank.json
   ```
   The output is 0–4 fit scores. `GEM` marks a strong fit (≥2.6) that appears on
   under 5% of this commander's EDHREC decks, or not at all. Cost is ~$0.10–0.20 per
   full pass, so be generous with passes. Useful variations:
   - Rank again with a *narrower* brief ("the sacrifice-outlet package only") to
     surface specialists that the whole-deck brief scores as merely supportive.
   - `--min-rank 3000` restricts to rarely played cards: pure gem hunting.
   - `--after 2024-01-01` looks at recent sets the crowd hasn't absorbed yet.

3. **Mechanic greps.** For each load-bearing mechanic in the brief, ask the
   literal question across the pool:
   ```bash
   ./edh jev grep "whenever a creature you control dies, this does something beneficial" \
       --ci "<commander>" --context decks/<slug>/<arch>/brief.md --threshold 0.6 --commander "<commander>"
   ```
   Phrase requirements as observable rules text, not vibes. Jev reads literally:
   "creates a token when a creature dies" works, "good aristocrats card" doesn't.
   Split compound needs into several greps.

4. **Precise search (Scryfall syntax).** Use it when you can state the pattern exactly:
   ```bash
   ./edh scry 'o:"whenever you sacrifice" -t:land' --ci "<commander>"
   ./edh scry 'otag:synergy-sacrifice mv<=3' --ci BG
   ./edh scry 'o:/proliferate|additional \+1\/\+1/ t:creature' --ci "<commander>"
   ```
   Scryfall's `otag:` covers far more tags than the local DB holds, so explore.

5. **Role fill.** For the slots every deck needs, sort by popularity and pick on
   fit. Then check for a less-played card that fits better:
   ```bash
   ./edh search --ci "<commander>" --tag board-wipe --limit 40
   ./edh search --ci "<commander>" --any-tag mana-rock --any-tag mana-dork --mv '<=2' --limit 40
   ./edh search --ci "<commander>" --lands only --limit 80        # mana base
   ./edh jev grep "land with a useful activated ability beyond producing mana" --ci "<commander>" --lands only
   ```

6. **Read, don't skim.** For each finalist, `./edh card "Name"` and read the whole
   text. Many "gems" are gems because they have a rider people missed. Many
   high-scored cards fail on a detail: symmetrical effects, "target opponent"
   versus "each opponent", sorcery speed, legend rule, exile vs. destroy.

## Without a Jev key

`jev` falls back to keyword overlap and says so. That output is a weak prior, not
a ranking. Do the semantic pass by reading instead. Dump focused pools
(`./edh search ... --limit 400 --width 220` or broad `scry` queries) and read
them in a subagent, so tens of thousands of tokens of card text don't land in
the orchestrator's context. Several narrow pools beat one giant one.

## What counts as a gem

A card earns "gem" when **all** of these hold:
- it scores high on fit for *this* plan (not just generically strong),
- few decks with this commander run it (EDHREC inclusion under ~5%, or absent),
- it beats, or does something different from, the staple it competes with.

Justify each in the deck notes in one line: *what it does here that the obvious
card doesn't*. A deck with 60 gems is a pile of cute cards; one with zero is a
netdeck. For most brackets 8–25 non-staple picks is healthy.

## Output (when you're a subagent)

Return a shortlist, grouped by role, with one line per card:
`Name — MV — why it's here (what it does for THIS plan) — staple/gem — EDHREC inclusion`.
Include 5–10 notable rejects with the reason. Rejects teach the builder as much
as picks do.
