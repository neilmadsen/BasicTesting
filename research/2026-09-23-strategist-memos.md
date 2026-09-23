# What the strategist's memos were missing

Follow-up to [pilot v2](2026-09-23-jev-pilot-v2.md). The question: compared with how a
strong player thinks about a Commander game, what do the strategist's per-turn memos
miss, and how much of that is missing *information* rather than missing *reasoning*?

## Method

`edhkit/memo_lab.py` works offline on a `--log-state` pilot log. It pairs each memo with
the board it was written on (325 memos from the v2.2 arm) and samples 20, stratified
into early game, mid game, late game and escalation re-plans.

- **Critique.** An expert reviewer (Opus 5.5, high effort) sees three things: the
  strategist's verbatim prompt, its memo, and information the strategist did not
  have, clearly labelled. The reviewer scores six dimensions of top-player thinking
  from 0 to 3:
  - threat by trajectory
  - answer budget
  - target state
  - win path
  - risk
  - sequencing

  It marks each shortcoming as a *reasoning* failure or an *information* gap, names
  the missing information, and writes the memo it would have written.
- **Blind A/B.** The same 20 boards get memos from a new strategist setup. A judge
  compares them with the originals in random order; it isn't told which is which and
  is warned that longer isn't better. The judge gets ground truth neither strategist
  had: our full list and the opponents' actual decklists. A sign test gives the
  p-value.

## v2: what was missing

Critic scores (0–3) over the 20 sampled v2 memos:

| threat | answers | target state | win path | risk | sequencing |
|---|---|---|---|---|---|
| 1.1 | 0.9 | 1.05 | **0.2** | 1.05 | 1.15 |

Shortcomings: 90 reasoning, 50 information.

The reviewer is harsh, and 2 means "solid". Four patterns recur:

- **No plan to win.** 17 of 20 memos had no closing plan and no clock comparison. The
  deck's closers (Kokusho loops, Gray Merchant, Vrock) are rarely named. That fits the
  pilot's weak win rate: it survived longer and closed slower.
- **Kill-on-sight blind spots.** Commander knowledge a strong player brings to the
  table was missing:
  - Sephiroth drains on every creature death and transforms on the fourth, so it has
    to die before any wipe.
  - Edgar's eminence makes tokens from the command zone, so killing Edgar doesn't
    stop them.
  - Sauron amasses whenever we cast a spell.
  - The Scarab God can exile Muldrotha from our graveyard and give its owner a copy.
  - Seal of Doom and Executioner's Capsule were earmarked for "the first commander
    that lands" in a pod where all three commanders are black, and both say
    "nonblack".
- **Arithmetic and rules.** Examples: Muldrotha "at four lands plus Birds" (it costs
  6); a graveyard land drop while Muldrotha was still in the command zone; Siren
  Stormtamer assigned to protect a planeswalker.
- **Information the strategist never had.** Of 140 shortcomings, 50 were information
  gaps, most of them card text and costs (16), our decklist (15) and game history
  (10). Two inputs were actively misleading:
  - The "deck plan" was the pre-build design brief. It named hypothetical cards
    ("Ravenous Chupacabra-style") instead of the real 99, so the strategist couldn't
    name tutor targets or count the answers still in the library.
  - `my_mana_available` came from Forge's AI heuristic, which counts each colour of a
    "Combo B G U" land as separate mana. A Triome counted as 3–4, so the strategist
    planned 8-mana turns on 5 lands.

## v3: the missing context, and a memo that must say how we win

`edhkit/strategist.py` (`--strategist-version v3`) supplies:

- **Our deck by zone**, with the builder's role notes. The library is what's left to
  tutor.
- **Full oracle text with mana costs** from the card DB, covering everything relevant
  in view: hand, graveyard, both battlefields, opponents' commanders, the stack, and
  our utility lands.
- **Opponent dossiers** (`gauntlet/dossiers/`, `edhkit/dossier.py`). One per
  commander, built from public data only: oracle text plus EDHREC themes and
  most-played cards, never the exact gauntlet list. Each covers:
  - PLAN
  - ENGINE
  - KILL ON SIGHT, saying plainly when killing the commander doesn't stop the engine
  - PUNISHES: what our plays feed
  - EXPECT
  - CLOCK
  - a deterministic INTERACTION profile (v3.1): the expected number of wipes,
    counters, graveyard hate and so on in a typical list, with inclusion rates
- **Mana counted from oracle text**, plus Forge's fixed count for the executor.
- **Game facts** from the Java side: commander tax, stolen permanents, monarch, and
  recent casts from Forge's public log.
- **A checklist and a new memo format.** The checklist runs before writing: lethal
  both ways, exact mana, rules, trajectory, answers, windows and exposure, target and
  win path. The memo then has six lines: THIS TURN / TARGET / WIN PATH / THREATS &
  ANSWERS / HOLD / REPLAN IF.

## Results

All comparisons are blind, on the same 20 boards, judged by Opus 5.5 at high effort
with ground-truth context.

| candidate | vs | result | sign test p | s / memo |
|---|---|---|---|---|
| v3 (context + format), medium effort | v2 original | **17–3** | 0.003 | 49 |
| v3, low effort | v2 original | 16–4 | 0.012 | 23 |
| v3 medium | v3 low | 15–5 | 0.041 | — |
| v3.1 (+ interaction priors, exposure check) | v3 | 9–11 | 0.82 | 44 |
| v3.1, high effort | v3.1 medium | 14–6 | 0.12 | 68 |
| **v3.1 medium + verify pass (medium)** | v3.1 medium | **17–2** | 0.001 | 104 |
| **v3.1 medium + verify pass (low)** | v3.1 medium | **17–3** | 0.003 | 72 |
| v3.1 low + verify (low) | v3.1 medium + verify (low) | 6–13 | 0.17 | 50 |

What the table says:

- **Most of the gain is information, not thinking.** v3 at the *same* low effort as
  v2 still wins 16–4. More effort adds a smaller further gain (medium beats low
  15–5).
- **A separate checking pass beats thinking harder in one pass.** A second call audits
  the draft line by line: mana against counted sources and tax, costs, targeting
  restrictions (colour, type, indestructible, ward), lane and graveyard rules, and
  lethal maths. It then returns a corrected memo. That beat the unchecked memo 17–2.
  One pass at high effort managed 14–6. The judge's reasons for preferring checked
  memos are the errors the audit targets: an illegal double land drop, two artifacts
  through Muldrotha's one-per-type lane, Blood Artist offsets, a "blocker" that can't
  block fliers.
- **The dossiers' interaction priors made no detectable difference** (9–11). They stay
  because they are what a strong player knows and cost nothing. Twenty boards can't
  see a small effect.
- Defaults are now `--strategist-version v3 --strategist-verify low`: a medium-effort
  draft plus a low-effort check, about 70 s per memo.

The same critic on the v3 memos (it saw the v3 prompt; the withheld information was
the opponents' actual lists):

| | threat | answers | target state | win path | risk | sequencing |
|---|---|---|---|---|---|---|
| v2 | 1.1 | 0.9 | 1.05 | 0.2 | 1.05 | 1.15 |
| v3 | 1.8 | 1.55 | 1.85 | **1.5** | 1.25 | 2.1 |

Information gaps fell from 50 to 32, and they changed character: 26 of the 32 are now
**what the opponents can do to us**. Examples:

- all three black decks run Toxic Deluge;
- the white deck holds Farewell, which also exiles our graveyard;
- the vampire deck has a second infinite (Sanguine Bond with Exquisite Blood);
- the Sauron deck runs about ten mana rocks.

Some of this only an exact list reveals. The category-level part is what the v3.1
interaction profiles supply: a white deck at bracket 3 holds about two wipes, a blue
one holds counters.

Risk is the dimension that moved least, and reasoning failures were still 92. That
led to the verify pass, which is where the next big gain came from.

## Game level

*Running:* a 24-game arm on the same pods as the v2 experiments, with the v3.1
strategist (medium effort, no verify pass). Results will be added here. Win rates at
this sample size can only detect large effects. The memo-level evidence above is the
stronger signal.

## Caveats

- The judge and critic are the same model family as the strategist. Blind ordering
  and ground-truth context reduce that bias but don't remove it.
- Twenty boards detect large effects only: v2 → v3 is large; v3 → v3.1 is not
  detectable.
- The same prompt gives noticeably different memos run to run, so single examples
  prove little.
- Memo quality is not game outcome. The executor has to follow the memo, and it
  controls only the hooked decision kinds. Mana payment, X values, modes, trigger
  order and multi-target choices stay with Forge. A memo that says "Toxic Deluge
  for X=11" or "keep {U} up for Stormtamer" can't make Forge pick that X or leave
  that Island untapped.
