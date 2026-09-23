# Commander deck lab

This repo builds, tests and delivers Magic: The Gathering Commander decks. A user
gives a commander and a bracket, and you (Claude Code) do the work: explore the
strategy space, scout cards, build one or more complete 100-card decks, check them
against the bracket rules, playtest them, and hand back proxy-ready lists.

**The user proxies everything.** Price is irrelevant. A $900 land and a 25-cent
uncommon compete on equal terms, and so do old cards and obscure ones. The whole
point of the tooling is to find the cards nobody plays because nobody found them,
not to rebuild the EDHREC average deck.

## Start here

- New deck request ("build me X at bracket N") → the **`brew`** skill (`/brew`).
  It orchestrates everything below and spawns subagents.
- Improving an existing list → **`tune-deck`**.
- "Find me cards that do X" → **`card-scout`**.
- Rules questions about brackets → **`brackets`**.
- Testing questions → **`playtest`**.
- Print/export → **`proxy-export`**.

Always run `./edh doctor` first in a new session. If the card DB is missing, run
`./edh setup` (about 3 minutes). If Forge isn't built and you'll need sims, start
`./edh forge setup` in the background (about 10 minutes) while you do strategy work.

## The toolkit (`./edh`, stdlib Python in `edhkit/`)

| Need | Command |
|---|---|
| Card details | `./edh card "Name" ["Name"...]` |
| Precise search (Scryfall syntax) | `./edh scry 'o:proliferate t:creature' --ci "Atraxa, Praetors' Voice"` |
| Offline filter search | `./edh search --ci BG --tag sacrifice-outlet --mv '<=2' --limit 40` |
| **Semantic screen of the whole pool** | `./edh jev rank --brief brief.md --ci "<commander>" --commander "<commander>"` |
| Semantic grep | `./edh jev grep "gives creatures an extra death trigger" --ci BG --context brief.md` |
| What the crowd plays | `./edh edhrec "<commander>" [--bracket 3]` |
| Normalise a list | `./edh deck deck.txt --write` |
| Stats + goldfish | `./edh analyze deck.txt` |
| Opening hands to eyeball | `./edh hands deck.txt -n 6` |
| Legality + bracket | `./edh validate deck.txt --bracket 3` |
| Forge pods vs gauntlet | `./edh sim deck.txt --bracket 3 --games 40` |
| A/B two versions | `./edh compare old.txt new.txt --bracket 3 --games 60` |
| Sim with our seat piloted by Jev (+ LLM strategist) | `./edh sim deck.txt --bracket 3 --pilot jev --strategist claude-cli` |
| Opponent pool | `./edh gauntlet build --bracket 3` / `./edh gauntlet list` |
| Proxy output | `./edh export deck.txt --format plain|moxfield|pdf` |
| What changed between versions | `./edh diff old.txt new.txt [--proxies-out new_cards.txt]` |

Role tags (`--tag`) come from Scryfall's community Tagger: `./edh tags list`.

**Jev** is TypeSafe's structured-decision model (docs.typesafe.ai). It is not a
chat model. It returns calibrated scores and probabilities cheaply, so
`jev rank` can judge every legal card in the color identity against a strategy
brief for a few cents. With no `TYPESAFE_API_KEY` in `.env`, the jev commands fall
back to crude keyword overlap and say so. In that case do the semantic screening
yourself with `scry` queries plus reading, or hand it to a `card-scout` subagent
to keep your own context clean.

## File layout for deck work

```
decks/<commander-slug>/
  README.md              ← the deliverable: options compared, recommendation, how to print
  strategies.md          ← archetypes considered (incl. rejected) and why
  <archetype-slug>/
    brief.md             ← strategy brief (also the Jev state; keep it < ~1500 words)
    deck.txt             ← canonical annotated list (`# role: why` notes on every nonland)
    proxies.txt          ← plain list for printing (`./edh export deck.txt --out proxies.txt`)
    notes.md             ← how to pilot, key lines, gems explained, test results, open questions
    candidates/          ← jev/scry outputs worth keeping
    sims/                ← Forge logs (gitignored) + summary.json
```

## Principles

- **Taste is the product.** The tools screen, count and simulate. Choosing is
  your job. Make real choices and defend them in the notes. When the strategy
  space for a commander has several genuinely different good answers, build
  each of them rather than averaging them into mush.
- **Hidden gems, not novelty for its own sake.** A gem is a card that fits *this*
  plan better than the staple would, or does something no staple does, and that
  few players run with this commander. Every deck should have some, and each
  one needs a one-line justification in its note. Staples stay where they are
  simply the best card for the slot.
- **Bracket is a contract.** `./edh validate` must PASS. Treat REVIEW items as
  real questions and answer them in notes.md.
- **Be honest about evidence.** The goldfish gives tight numbers on mana
  questions. Forge sims give noisy numbers on "does this deck function against a
  table". At 40 games the 95% CI on win rate is about ±13 points, and the Forge
  AI misplays combo, control and politics. Never present a sim result as more
  than it is.
- Keep your main context lean. Push bulk reading (big card pools, long game logs)
  into subagents and keep their conclusions.
