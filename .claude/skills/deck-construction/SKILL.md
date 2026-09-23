---
name: deck-construction
description: How to assemble a 100-card Commander deck from a brief and a candidate pool — slot budgeting by role and bracket, mana base construction, curve discipline, and the annotated deck.txt format. Use when turning candidates into a list or restructuring a list.
---

# Deck construction

## Budget the 99 before picking cards

Start from the brief's plan, not from a template. Then sanity-check it against
these ranges for brackets 2–4 (B1 bends toward theme; B5 is a different game):

| Slot | Typical | Bend it when |
|---|---|---|
| Lands | 35–38 | Fewer with cheap curve + many rocks/dorks (B4: 31–34 plus fast mana). More for landfall, lands-matter, or a 6+ MV commander. |
| Ramp | 9–12 | Commander at 5+ MV, or a big-mana plan: 12–15. Low curve aggro: 6–8. |
| Card advantage | 9–12 | The commander *is* the draw engine: 6–8. Count repeatable engines at ~2× one-shots. |
| Targeted interaction | 8–12 | Include some instant-speed answers. Cover artifacts/enchantments, not just creatures. |
| Board wipes | 2–4 | Go-wide decks run 0–1 and lean on one-sided wipes instead. Control runs 4–6. |
| Protection | 2–5 | Voltron or commander-dependent plans: 5–8. |
| Win conditions | 3–6 real ones | Say explicitly which cards end the game. "Value" is not a wincon. |
| Plan/engine cards | the rest | This is where gems live. |

A card can fill two slots (an Eternal Witness is recursion *and* card advantage),
but don't double-count cheerfully. `./edh analyze` shows the tagger's role
counts. Treat them as a checklist, not a score.

## Curve

Average nonland MV around 3.0 (B2–3). Watch the top end: more than 8–10 cards at
MV 6+ without a cheat or ramp plan means clunky draws. Two-drops matter more than
you think: they're what you do on turn 2 while you set up.

## Mana base (proxies = no budget excuse)

- Land count: set it from the goldfish, not superstition. After a draft, run
  `./edh analyze`, then add or cut 1–2 lands or cheap ramp and re-run until the
  commander lands by its MV+1 in ≥75–80% of games, T4 screw stays ≤ ~10–12%, and
  flood stays ≤ ~15%.
- Colors: duals that enter untapped first (original duals, shocks, fetches, and
  pain/check/fast/battle/verge lands by fit), then fixing rocks. With proxies,
  use the best duals. Check `color pips vs land sources` in `analyze`. A color
  that's 30% of your pips needs roughly 30%+ of your colored sources. Early pips
  (1–2 MV spells) need more than late ones.
- Utility lands are free value but cost colored sources. 3–6 is typical. Screen
  with `./edh jev grep "land with a useful ability beyond producing mana" --lands only`.
- Basics still matter for basic-land ramp and against nonbasic hate.

## Game Changers and bracket budget

B1–2: none. B3: at most three, so spend them on what *this* deck most needs, not
on the most famous ones. B4–5: unlimited, but still earn each slot. Check with
`./edh validate` early; don't discover a violation after tuning.

## deck.txt format

```
# Commander
1 Meren of Clan Nel Toth

# Creatures (31)
1 Viscera Seer  # sac outlet: free, scry smooths draws — the cheapest loop enabler
1 Priest of Forgotten Gods  # GEM engine: turns two sacrifices into ramp+draw+edict; 3% on EDHREC
...
# Lands (36)
1 Overgrown Tomb
14 Swamp
```
- Every nonland card gets `# role: why`. Mark gems with `GEM`. Lands may skip notes.
- Run `./edh deck deck.txt --write` to normalize grouping and order (it keeps notes).
- Maybeboard: a `# Maybeboard` section is fine for near-misses. Validation ignores it.

## Before calling a list done
1. `./edh validate deck.txt --bracket N` passes.
2. `./edh analyze deck.txt` has role counts in range or deliberately off (say why
   in the notes), and goldfish targets are met.
3. `./edh hands deck.txt -n 6`: read the hands. Would you keep them? Do they
   *do* something by turn 3?
4. Explain the win in one breath.
