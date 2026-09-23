# Muldrotha, the Gravetide: three builds for Bracket 3

**Verdict.** Build **Groundskeeper** first. It is the most distinctive of the
three and has the best mana: Muldrotha lands on turn 5.1 on average and on curve
89% of the time. It turns the land lane, which the crowd barely uses on purpose,
into card draw, ramp and a token army, and its critic would sit down with it
unchanged. Build **Undertaker's Toolbox** if you like control. It has 26
removal effects, most of which come back every turn, and in play it's the
most interactive and least expected deck at the table. It is also the slowest to
close. **Gravetide Value** is the crowd's plan done well, with some new-card gems
(the Emeritus prepare creatures). It's the benchmark: build it if you want the
familiar Muldrotha experience.

The sims don't rank these. All three 95% intervals overlap, and Forge's AI can't
play several load-bearing cards in each list. See [Evidence](#evidence).

## At a glance

| | Groundskeeper | Undertaker's Toolbox | Gravetide Value |
|---|---|---|---|
| Plan | Lands are spells: fetch, cycling, horizon and sacrifice lands replay from the graveyard; landfall token army | Recurring-removal control: sacrifice-for-effect permanents in every lane, recast each turn | Self-mill, ETB creatures, reanimation; Jarad and big bodies close |
| Muldrotha, avg first cast (goldfish) | **T5.1** (89% on curve) | T5.7 (71%) | T5.7 (72%) |
| T4 mana screw / flood | 5% / 4% | 8% / 2% | 7% / 2% |
| Lands / avg MV (nonland) | 39 / 3.17 | 36 / 2.73 | 36 / 3.24 |
| Targeted removal / wipes | 7 / 2 | **26 / 4** | 20 / 6 |
| Game Changers | Field of the Dead, Mox Diamond, Survival | Demonic Tutor, Survival, The One Ring | Rhystic Study, Survival, The One Ring |
| Forge sim (32 games, 4-player B3 pods) | 3 wins, 9% (CI 3–24%) | 6 wins, 19% (CI 9–35%) | 5 wins, 16% (CI 7–32%) |
| Round we win / die (sim) | 8.3 / 9.8 | 13.3 / 10.6 | 10.2 / 10.3 |
| Graveyard casts per game (sim) | 1.9 spells + 2.5 lands | 4.7 spells + 1.4 lands | 2.4 spells + 1.3 lands |
| Non-staple picks (marked GEM) | 15 | 17 | 13 |
| Pilot complexity | High: 8+ triggers per land late | High: six lanes, sacrifice timing | Medium |
| Tell the table before the game | Lumra/Nantuko/Zuran Orb infinite (turn 7+) | Massacre Wurm and Ratchet Bomb recur every turn | Tutor density |

All three pass `./edh validate --bracket 3`.

## Groundskeeper → [`groundskeeper/deck.txt`](groundskeeper/deck.txt) · [notes](groundskeeper/notes.md) · [proxies](groundskeeper/proxies.txt)

Muldrotha lets you make your land drop from the graveyard. That doesn't give an
extra drop, but it costs no mana. So a fetch land, a horizon land or a cycling
dual becomes a spell you cast every turn for free. The deck stacks three
mechanisms on top:
- **Graveyard-land permission before Muldrotha:** Mole Man, Ramunap, Icetill,
  Life from the Loam, Ancient Greenwarden.
- **Extra land drops:** Azusa, Dryad, Exploration, Oracle, Aesi.
- **Lands that return straight to the battlefield:** Undergrowth Recon,
  Blossoming Tortoise, Lumra. They enter tapped, and Amulet of Vigor untaps them.

Payoffs trigger both on lands entering (Scute Swarm, Greensleeves, Avenger, Field
of the Dead, Ob Nixilis) and on lands leaving (Titania, Scouring Swarm, Gitrog).

- **Defining cards:** Undergrowth Recon, Mole Man, Amulet of Vigor, Titania pair, Field of the Dead.
- **Best gems:**
  - **Scouring Swarm:** every land we sacrifice makes a flier.
  - **Mole Man:** Ramunap plus a 1/1 per landfall for the same 3 mana.
  - **Greensleeves:** a 3/3 per landfall.
  - **Elvish Reclaimer:** a 1-drop that repeatedly tutors Field of the Dead or a Memorial.
  - **Zuran Orb:** a free land sacrifice at instant speed, and the lands come back.
- **Watch out:** interaction is thin (7 targeted removal, 1 counterspell). It
  survives wipes but loses races to fast aggro and drain decks.

## Undertaker's Toolbox → [`undertaker/deck.txt`](undertaker/deck.txt) · [notes](undertaker/notes.md) · [proxies](undertaker/proxies.txt)

Every permanent type is a removal spell. With Muldrotha out, each of her lanes
recasts one from the graveyard every turn:
- **Artifact:** Executioner's Capsule, Walking Ballista, Ratchet Bomb.
- **Enchantment:** Seal of Doom, Sinister Concoction.
- **Planeswalker:** walkers we minus to death.
- **Battle:** Invasion of Innistrad.
- **Creature:** Sheoldred's edict, Massacre Wurm.

Claws of Gix sacrifices a spent saga, walker or battle for {1} so it comes back
next turn. The deck closes with drains: Vrock, Kokusho, Gray Merchant,
Marionette Apprentice, The Coming of Galactus.
- **Defining cards:** Claws of Gix, Executioner's Capsule, Seal of Doom, Massacre Wurm, Vrock.
- **Best gems:**
  - **Claws of Gix:** the piece that closes the engine.
  - **Vrock:** in this deck it reads "each opponent loses 3 every end step".
  - **Baba Lysaga:** sacrifice a land and an artifact creature, draw 3 and drain 3, then Muldrotha replays both.
  - **Dalek Drone:** an artifact creature, so either lane can recast it.
  - **Ratchet Bomb:** a token wipe you re-arm every turn.
- **Watch out:** it wins late. Sim wins came around round 13. Invasion of Fiora
  was cut in the critique round because it kills 18 of our 24 creatures and
  loops into a creature lock.

## Gravetide Value → [`gravetide-value/deck.txt`](gravetide-value/deck.txt) · [notes](gravetide-value/notes.md) · [proxies](gravetide-value/proxies.txt)

Self-mill, ETB creatures recast each turn, reanimation. After the critique it
has a free sacrifice outlet (Ashnod's Altar) and a defined kill: Jarad sacrifices
a recurring fatty, and each opponent loses 5–7 life per activation.
- **Defining cards:** Ashnod's Altar, Jarad, Emeritus of Woe, Ravenous Chupacabra, Grave Titan.
- **Best gems:**
  - **Emeritus of Woe:** a 5/4 that casts a copy of Demonic Tutor, and prepares again whenever two creatures die in a turn.
  - **Emeritus of Ideation:** a 5/5 flyer that casts a copy of Ancestral Recall.
  - **Seedship Broodtender:** self-mill that later reanimates.
  - **Dreadhound:** drains each opponent for every creature that dies or is milled.
  - **Overlords:** cheap impending casts through the enchantment lane.

## Evidence

- **Goldfish** (20k trials each) is reliable for the mana questions, and all
  three decks meet the targets.
- **Forge sims** (32 games each, 4-player pods against bracket 3 EDHREC average
  decks) are a functional check, not a ranking:
  - *The intervals overlap.* Groundskeeper's 9% and Undertaker's 19% are not
    distinguishable at this sample size.
  - *Forge's AI can't play the engines.* The cards it never cast include
    Groundskeeper's Scapeshift, Sylvan Library and Toxic Deluge, Undertaker's
    Claws of Gix and Mishra's Bauble, and The One Ring in both of the decks
    that run it. The AI never casts The One Ring in any deck.
  - *It underuses Muldrotha.* It casts 2–5 spells a game from the graveyard,
    where a human with 3–4 Muldrotha turns would cast far more. It recurs cheap
    sacrifice-for-effect permanents well and big creatures badly, which likely
    explains why Undertaker measures best here.
  - *What's real:* all three builds die around round 10 to linear creature and
    drain decks. Across the three final runs, Y'shtola won 18 of its 30 games,
    Giada 9 of 15 and Atraxa 10 of 21, against a 25% baseline. Some of that
    is Forge's bias toward linear decks, and some is real: Muldrotha is a
    six-mana engine commander. Expect to be the table's archenemy late, not
    early.
- **Critique round.** An independent critic reviewed each deck, and every
  critique changed the list:
  - It caught a misread wipe (Invasion of Fiora) in Undertaker.
  - It found a missing sacrifice outlet and no defined kill in Gravetide Value.
  - It found tapped-land and land-type rules errors in Groundskeeper's notes.
  - Each deck's `notes.md` has a *Critique round* section.

## Assumptions and open questions

- There was no intake round (demo run): bracket 3, proxies, no pet cards,
  three builds.
- Groundskeeper's Lumra + Springheart Nantuko + Zuran Orb loop is a genuine
  infinite. It needs 4 specific cards and 10–11 mana, and Survival finds three of
  them. It fits B3's allowance for late multi-card combos, but disclose it
  before the game, or cut Zuran Orb.
- Twilight Diviner copying a prepared Emeritus (Gravetide Value) is unverified
  rules-wise. The deck doesn't depend on it.
- The strategy map's first draft wrongly treated Muldrotha's graveyard land as
  an extra land drop. The Groundskeeper builder caught it, and every deck is
  built on the correct rule.

## How to print

```bash
./edh export decks/muldrotha-the-gravetide/groundskeeper/deck.txt --format pdf   # 3×3 true-size sheets
```

Print at 100% ("actual size"). Or paste `proxies.txt` into MPCFill or any proxy
printer. You probably own the basics, so remove them from a copy first if you
don't want to print them.
