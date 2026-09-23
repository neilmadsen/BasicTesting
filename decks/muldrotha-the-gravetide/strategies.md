# Muldrotha, the Gravetide: strategy map (Bracket 3)

> During each of your turns, you may play a land and cast a permanent spell of each
> permanent type from your graveyard.

**What the card actually converts.** Muldrotha turns a graveyard into a second hand
that holds one card per permanent type and refills every turn. Muldrotha costs six
and has no protection, so the deck has to function before she lands and has to
make her worth the removal she'll draw. Each permanent type is its own recursion
lane, and each lane rewards a different kind of card:

- **Land lane**: permission to make your land drop from the graveyard. It is not
  an extra land drop: that still takes Azusa, Exploration and the like. It costs
  no mana, so any land that sacrifices itself for value (fetches, horizon lands,
  cycling lands) repeats every turn. The crowd uses this lane least deliberately.
  *(Corrected during the build: the first draft of this map wrongly called it a
  free extra land. The Groundskeeper builder caught it.)*
- **Artifact and enchantment lanes**: any permanent that *sacrifices itself for
  an effect* becomes a repeatable spell. A one-shot removal artifact becomes
  removal every turn.
- **Creature lane**: ETB creatures become repeatable ETB effects. This is the
  classic use, well mapped by EDHREC.
- **Planeswalker lane**: a walker you minus to death is a repeatable sorcery.
  Expensive, but most Muldrotha lists underuse it.

**Crowd baseline** (EDHREC, 2,567 decks at B3): Reanimator, Graveyard, Self-Mill,
Mill. The staple core is Spore Frog, Sakura-Tribe Elder, Eternal Witness, Kaya's
Ghostform, Seal of Primordium, Gravebreaker Lamia and Animate Dead. "Lands Matter"
has only 81 decks.

## Candidates

| # | Archetype | Thesis | Verdict |
|---|---|---|---|
| A | **Groundskeeper** (lands recursion + landfall) | Fetches, cycling lands and sac-for-value lands get replayed from the graveyard every turn, so the land drop itself becomes ramp, card draw and landfall triggers. Extra-land-drop effects multiply it. Win with landfall token armies. | **Build.** Most distinct from the crowd, uses the cheapest lane, and the gem density is high (horizon lands, cycling duals, Six, Ancient Greenwarden). |
| B | **Undertaker's Toolbox** (recurring removal control) | Fill the artifact, enchantment and planeswalker lanes with permanents that sacrifice themselves for removal or cards (Executioner's Capsule, Seal of Primordium, Cryogen Relic, minus-to-death walkers). With Muldrotha out, the table loses a permanent every turn. | **Build.** A control deck no one on EDHREC is building on purpose. Good at B3, where decks can't simply out-race it. |
| C | **Gravetide Value** (self-mill + ETB creatures + reanimation) | The best version of the crowd plan: mill aggressively, recur ETB creatures, reanimate a few premium fatties, grind. | **Build as the benchmark.** It's the honest comparison point. If A and B can't beat it in sims or on paper, that's worth knowing. |
| D | Combo (Hermit Druid, Dread Return lines, Mikaeus loops) | Deterministic kills from the graveyard. | Reject for B3. The fast lines are early two-card territory, and the slow ones are worse versions of C. |
| E | Mill opponents | Muldrotha recurring mill artifacts. | Reject. It's slower than every other plan, and mill in a 4-player pod means milling 300 cards. |
| F | Birthing Pod chains | Pod and Prime Speaker lines with creature recursion. | Folded into C as an option, not its own deck. Forge's AI also plays Pod badly, which would blind the sims. |

## Assumptions (no intake round, demo run)
- Bracket 3: at most three Game Changers, no MLD, no early two-card infinites.
- Proxies, so no budget limit. A best-in-slot mana base is assumed.
- Three builds, because the lanes support three genuinely different decks.
