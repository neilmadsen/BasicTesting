# Obeka, Splitter of Seconds: two control builds for Bracket 3

**Verdict.** Build **Twice-Told** first. It's the more creative of the two and the more consistent. It turns
a mechanic no Obeka deck plays into the engine: an extra upkeep counts as "your next upkeep", so rebound
spells cast before combat come back the same turn, and with Cast Through Time, every instant and sorcery does.
It has the most card flow (20 draw/selection effects), three real answers to a creature board, and five
distinct ways to win. The one most likely to surprise a table is the Ring snowball: Obeka's counters compound
through her own upkeeps, giving 21 commander damage in two or three hits.

Build **The Long Morning** if you'd rather grind with permanents: steal the table's best creatures, reanimate
their dead, and let Court of Ire copies burn everyone, while seven counterspells keep the board honest. It has
more interaction than Twice-Told (32 targeted answers) but much less card flow (9). Its engine takes longer to
assemble, and its games are long, political and full of trigger-ordering puzzles.

Neither is the crowd's Obeka deck (Courts, upkeep Rings, monarch, As Foretold). That plan is documented on
EDHREC and plays the same game every time, so I used it only as a comparison: every staple it runs that these
lists don't is answered under "Omitted staples" in each deck's notes.

The tests don't rank the two builds. Both lose most simulated games to go-wide creature decks, and the
samples are far too small to separate them. See [Evidence](#evidence).

## At a glance

| | Twice-Told | The Long Morning |
|---|---|---|
| Plan | Grixis draw-go. When Obeka connects, rebound and Cast Through Time spells resolve twice that turn, and Galvanoth, Panoptic Mirror and the Rings fire every upkeep | Grixis permanent control. Upkeep triggers remove, steal, reanimate and draw, and Obeka multiplies them |
| Win paths | Ring commander-damage snowball; Mirror + Delayed Blast Fireball (5 to each opponent per upkeep); doubled burn turn; World at War triple combat; attrition | Court of Ire cannon (Estrid's Invocation and Extravagant Replication copies); theft and reanimation beatdown; Demonic Pact handed over; burn reach |
| Obeka first cast (goldfish) | T3.9 (83% on curve) | T3.7 (89% on curve) |
| Screw at T4 / flood | 7% / 2% | 8% / 2% |
| Engine online by T6 (its own honest spec) | 42% with a real evasion card, 72% relying on menace | 27% full spec, 45% without the evasion clause (majority by T7) |
| Interaction: targeted / wipes / counters | 23 / 6 (3 that clear 4/4s) / 7 | 32 / 4 / 7 |
| Card draw/selection | 20 | 9 |
| Claims audit (notes checked against oracle text) | 0 wrong after fixes (earlier runs: up to 26 findings, 1 wrong) | 0 wrong after fixes (earlier runs: up to 5 wrong and 9 overstated) |
| Gem audit (vs the staple each displaced) | 20/21 judged better (single-order run) | 16 better, 1 split, 1 staple better (both orders) |
| Forge smoke test (16 games, Forge's AI) | 1 win, 6% (CI 1–28%), revision-1 list | 0 wins, 0% (CI 0–19%), revision-1 list |
| Pilot confirmation (4 games, our AI pilot) | 0 wins (CI 0–49%); every engine fired | 1 win on round 13 (CI 5–70%); won through Court of Ire copies |
| Pilot complexity | High: many upkeep triggers, ordering matters | Very high: many trigger targets per upkeep, Pact sequencing, tokens to track |
| Game Changers | Panoptic Mirror, Fierce Guardianship, Demonic Tutor | Rhystic Study, Cyclonic Rift, Fierce Guardianship |
| Tell the table first | Mirror + Delayed Blast Fireball is a tutorable lock that creature decks can't play through | Pact + Puca's Mischief kills one player; doubling Extravagant Replications is explosive |

Both pass `./edh validate --bracket 3`.

## Twice-Told → [`twice-told/deck.txt`](twice-told/deck.txt) · [notes](twice-told/notes.md) · [proxies](twice-told/proxies.txt)

On turns Obeka doesn't connect, this is a normal draw-go deck: hold up a counter or a kill spell, trade, and
draw ahead. On turns she does, everything cast from hand before combat damage happens twice. Rebound fires in
her first extra upkeep, and Galvanoth, Panoptic Mirror, Court of Ire and the Rings fire in each one.

- **Defining cards:** Cast Through Time, Panoptic Mirror, Ring of Evos Isle, Galvanoth, World at War.
- **Best gems:**
  - **Delayed Blast Fireball:** deals 5 instead of 2 when cast from exile, which rebound, the Mirror's copy
    and foretell all are. That makes it a one-sided sweep and the Mirror's clock.
  - **World at War:** its rebound in Obeka's extra upkeep adds a second extra combat.
  - **Ojer Pakpatiq:** Cast Through Time for instants at 4 mana, and it comes back as a land.
  - **Sword of Wealth and Power:** +2 power means two more upkeeps per hit, and a hit copies the next
    rebound cast.
  - **Ring of Xathrid:** the second Ring, which doubles the commander-damage snowball.
- **How to pilot:**
  - Main phase 1: cast rebound spells.
  - Combat: connect.
  - Extra upkeeps: order Thassa's scry, then Galvanoth, then Theater of Horrors.
  - Main phase 2: sorcery-speed follow-up.
  - Never use X spells as rebound or Mirror targets (free casts make X = 0).
  - Watch for decking: Theater of Horrors' exile is mandatory.

## The Long Morning → [`long-morning/deck.txt`](long-morning/deck.txt) · [notes](long-morning/notes.md) · [proxies](long-morning/proxies.txt)

Permanents that act at the beginning of your upkeep, behind counters and cheap removal. Each upkeep Court of
Ire deals damage, Virtue of Persistence reanimates from any graveyard, Frenzied Fugue and Dominus of Fealty
steal, Legacy's Allure, Torch Song and Vile Requiem charge, and Phyrexian Arena draws. Every point of damage
Obeka deals adds another round of all of it.

- **Defining cards:** Court of Ire, Estrid's Invocation, Virtue of Persistence, Extravagant Replication,
  Demonic Pact.
- **Best gems:**
  - **Estrid's Invocation as a second Court of Ire:** it flickers every upkeep, so we're the monarch again
    before the 7-damage triggers resolve.
  - **Legacy's Allure, Vile Requiem and Torch Song:** each gains a counter every upkeep, then is sacrificed
    at instant speed to steal, sweep or burn.
  - **Ophiomancer:** a deathtouch blocker in every upkeep, opponents' included, and a Goblin Bombardment ping
    per upkeep.
  - **Shimmerwing Chimera and Teferi's Time Twist:** each resets Demonic Pact so it never reaches its fourth
    mode.
  - **Puca's Mischief:** a value swap every upkeep, and the Pact kill.
- **How to pilot:**
  - Deploy upkeep pieces *before* combat.
  - Order our triggers deliberately: Pact before its exit, Estrid's flicker before the Court damage.
  - Sacrifice borrowed creatures before cleanup.
  - Track tokens with dice.
  - Remove opponents' "each upkeep" punishers before a long turn: they hit us in every extra upkeep.

## Evidence

- **What's solid.**
  - The mana: both goldfish cleanly, with Obeka on curve 83–89% and screw under 10%.
  - The rules: every load-bearing interaction was checked against oracle text by a separate audit, and
    again by a critic.
  - The mechanisms: in piloted games, rebound recasts, Galvanoth, Court of Ire, Frenzied Fugue, Legacy's
    Allure and the Replication copies of Court all fired in Obeka's extra upkeeps exactly as the notes
    describe.
- **What's weak.** Win rates.
  - **Forge smoke test:** 1/16 and 0/16, both on the revision-1 lists. Forge's AI can't cast 4–11 of each
    deck's cards, and it plays control badly.
  - **Pilot run:** 0/4 and 1/4. Four games rank nothing.
- **One real pattern:** both decks lost mostly to go-wide creature decks (Giada's angels, Edgar's vampires)
  around round 10. The critics flagged the same hole. Both revisions added sweepers and an instant-speed answer
  to alpha strikes (Storm's Wrath and Aetherize; Ophiomancer and Aetherize), but nothing has tested those
  revisions over enough games to say they fixed it. If your table is creature-heavy, the first swaps are listed
  under "Swaps considered" in each deck's notes.
- **One harness bug found:** our pilot failed to pay for a spell through a Signet fed by another rock (open item
  T in `research/bugs/ledger.md`). It cost Long Morning a Demonic Pact cast in one game. It's a tooling defect,
  not a deck problem.

## Iteration: why the decks lost, and what changed

Lost piloted games were diagnosed from their logs instead of by playing hundreds more. `research/race.py`
marks the turn the eventual winner's board got out of hand and lists what we held. `./edh critical` replays
that exact board as a Forge scenario over several seeds, so a fix can be tested on the position that decided
the game.

**Deck: answer density.** Both lists held a real creature sweeper by turn 7 in only about 35% of games. The
changes:
- **Long Morning revision 3:** Storm's Wrath, Aetherspouts, Blasphemous Act and Decree of Pain. A board answer
  is held by turn 7 in 74% of games.
- **Twice-Told revision 3:** Aetherspouts and Evacuation as board answers, plus Baleful Strix, Silent Arbiter,
  Propaganda and Court of Embereth for board presence and as attack deterrents.
- **Twice-Told revision 4:** a scenario replay showed that 4-damage sweepers leave Edgar's counter-pumped
  vampires alive. With Storm's Wrath swapped into our hand on that board, we died in 2 of 3 seeds. Blasphemous
  Act and Damnation replaced Storm's Wrath and Languish. A board answer is held by turn 7 in 70% of games, and
  one that scales with the threats in 59%.

**Pilot: three fixes** (ledger #95–#97):
- **Re-planning at the start of our turn.** Damage taken while we were tapped out never triggered a re-plan,
  so a two-turn-old memo tapped us out at 19 life.
- **Planned sweepers beat Jev's own pick.** Jev scored a planned Toxic Deluge 0.06 against Shimmerwing Chimera.
  The rule covers board answers only: forcing *every* planned play lost a blind judge 23–60.
- **Combat information.** An attack trigger on the stack hid a lethal attack from the pilot, and it passed on
  Aetherspouts with 13 mana open. Now the attack at us is always visible, and a lethal one gets answered. In
  scenario replays of that board, Aetherspouts was cast in 3 of 3 seeds.

**Validation** (8 piloted games each, strategist every turn):
- **Results:** Twice-Told revision 4 won 1, lost 4, and 3 games hit the 45-minute clock. Long Morning
  revision 3 won 2 of 8. Earlier piloted runs were 0 of 4 and 1 of 4. That's still far too few games to call
  a win rate, and the third pilot fix came after these games.
- **What the losses show now:**
  - Half had a real answer in hand at the decisive turn but the wrong kind, or one the pilot didn't use. The
    pilot cases are fixed above.
  - The other half drew no answer: at 70–74% coverage, some games won't have one.
  - Edgar and Giada remain the hardest matchups. Their boards grow through +1/+1 counters, so answers that
    scale matter more than the number of sweepers.

## Assumptions and open questions

- **Bracket 3.** You didn't name one, so I used the bracket of the earlier builds; both decks sit at its strong
  end. At bracket 2, cut the Game Changers and the explosive lines. At bracket 4, both can add fast mana.
- **Rule-0 talking points** (both legal at B3; answered in each deck's notes):
  - Mirror + Delayed Blast Fireball;
  - the Ring snowball;
  - Demonic Pact + Puca's Mischief;
  - doubling Extravagant Replications (which needs Estrid's Invocation copying Replication first).
- **Rejected archetypes** and why are in [`strategies.md`](strategies.md): the crowd upkeep pile, suspend,
  extra combats, and Herald of Leshrac land theft (functionally mass land denial).

## How to print

`./edh export decks/obeka-splitter-of-seconds/<deck>/deck.txt --format pdf` gives true-size 3×3 sheets.
Alternatively, paste `proxies.txt` into MPCFill or a proxy printer.
