# Obeka, Splitter of Seconds — The Long Morning (Bracket 3)

Commander: Obeka, Splitter of Seconds {1}{U}{B}{R} — Legendary Creature 2/5. Menace. Whenever Obeka deals
combat damage to a player, you get that many additional upkeep steps after this phase.

**Thesis.** Fill the board with *answers* that trigger at the beginning of your upkeep, then let Obeka run
them two or three times a turn. Each Obeka hit becomes several of these at once:
- Virtue of Persistence: reanimate a creature from *any* graveyard, under our control.
- Culling Scales: destroy the lowest-mana-value nonland permanent.
- Court of Ire: 2 damage to any target, 7 while we're the monarch.
- Frenzied Fugue: steal the enchanted permanent and untap it.
- Parasitic Implant: kill the enchanted creature.
- Demonic Pact: 4 damage, two discards and two draws in one turn, then get rid of it before its fourth
  mode.
- Conjured Currency: a permanent swap.
- Steady draw: Phyrexian Arena, Staff of Nin.

The table's threats die, change sides, or come back for us from their graveyards. Counterspells cover
the gaps while the engine builds. It's a control deck that grinds through permanents, not spells, and
gets stronger the longer the game goes.

**Win conditions** (more than one):
1. Turn the table's best creatures into ours (Virtue reanimation, theft) and attack with them alongside
   an evasive Obeka.
2. Court of Ire with monarch: 7 damage to any target per upkeep, so 14–21 on an Obeka turn. Plus
   upkeep drain and burn.
3. Demonic Pact as a weapon: fire its three good modes, then give it to an opponent (Donate, Harmless
   Offering, Shifting Loyalties, Bazaar Trader-style effects) so they reach "you lose the game". Bracket 3
   REVIEW: a two-card deterministic kill of one player, not an infinite. Answer it in notes.md. Also have
   a safe exit (bounce it to hand, sacrifice it, flicker it) so Pact is never a liability.

**Engine.**
- 10–14 "at the beginning of your upkeep" permanents that remove, steal, reanimate or draw.
- Evasion and protection for Obeka.
- Recursion for the engine pieces (they will get removed).
- Enough cheap interaction to survive until the engine runs.

**Wants.**
- Upkeep-triggered removal, theft and reanimation. Browse the pool for "at the beginning of your upkeep"
  with destroy, damage, gain control, onto the battlefield under your control, sacrifices, or discards:
  most of the good ones are unplayed here.
- Ways to give away or reset Demonic Pact.
- Graveyard-filling that fuels Virtue (opponents' creatures die to our removal, so this is partly
  self-fuelling).
- Protection for the engine: counterspells, Padeem-style hexproof for artifacts, recursion for
  enchantments.

**Avoid.**
- "At the beginning of each upkeep" / "each player's upkeep" effects that hit the active player: in our
  extra upkeeps, that's us.
- Cumulative upkeep, echo, vanishing, and "sacrifice unless you pay" costs (paid several times).
- Pacts cast before combat.
- Culling Scales when our own cheap permanents (tokens, Sol Ring, Treasures) would be the lowest MV:
  plan around it or play it knowing the risk.
- Upkeep effects that are just random value.

**Interaction plan.** 12+ pieces: counterspells (~5, some cheap), spot removal for every permanent type,
1–2 wipes (ideally one that spares a small board of enchantments and artifacts), graveyard hate only if it
doesn't fight Virtue.

**Bracket constraints.** B3: at most 3 Game Changers. No two-card infinite combos; no extra-turn chains;
no mass land denial (no Herald of Leshrac).

**Targets.** Lands ~36 (utility: Rogue's Passage), ramp ~10, card draw ~9, interaction ~13, upkeep
engine permanents ~12, evasion/protection for Obeka ~5. Deviate deliberately.

**User preferences.** Proxies everything; price is irrelevant. Likes control and creativity, not one-note.
The deck should have real decisions on every turn.

```engine
name: Upkeep answers online
by: 6
commander
2 of: Virtue of Persistence; Court of Ire; Frenzied Fugue; Demonic Pact; Legacy's Allure; Enslave; Gisa, Glorious Resurrector; Dominus of Fealty; Puca's Mischief; Vile Requiem; Recantation; Xanathar, Guild Kingpin; Fatal Attraction; Torch Song; regex:at the beginning of your upkeep, [^.]*(destroy|damage to any target|gain control|under your control|sacrifices|discards)
1 of: regex:can't be blocked; regex:protection from; tag:gives-hexproof; Ring of Evos Isle; Untimely Malfunction
tutors: Grim Tutor; Diabolic Intent
```

```engine
name: Interaction held up
by: 5
held 2 of: tag:counterspell; tag:spot-removal; tag:creature-removal
```

```engine
name: Board answer held
by: 7
held 1 of: Toxic Deluge; Aetherize; Cyclonic Rift; Storm's Wrath; Blasphemous Act; Aetherspouts; Decree of Pain
tutors: Grim Tutor; Diabolic Intent
```


## Builder changes (long-morning build)

- **Culling Scales cut.** It must target the lowest-MV nonland permanent among all players. At a B3 table that
  is almost always a Treasure, a token or a 1-mana rock (often ours: Sol Ring, Parasitic Implant's Myr), so it
  never reaches a real threat. The slot went to targeted upkeep removal (Strangling Grasp, Vile Requiem).
- **Conjured Currency cut.** Once it swaps, the opponent controls it and swaps it for our best permanent on
  their upkeep. Puca's Mischief does the swap and keeps the engine on our side.
- **Donate / Harmless Offering cut.** With Demonic Pact, `validate --bracket 3` classes them as a cheap
  (total MV 7) two-card combo, which is a FAIL, not a REVIEW. The bracket is a contract, so the only kill route
  left is Puca's Mischief (an upkeep engine piece in its own right). Pact is now mainly a resettable value engine:
  three modes, then Teferi's Time Twist, Vedalken Mastermind, Get Out, Alchemist's
  Retrieval, Recantation or Otawara picks it up or resets it.
- **Engine spec** lists the upkeep answers actually in the deck (the original list named two cut cards).
- **Revision 2 (after critic review):** Vengeful Strangler → Ophiomancer (Grasp's sacrifice is "of their choice",
  so token decks feed it a Treasure; Ophiomancer is a deathtouch blocker every upkeep), Crystal Chimes → Fatal
  Attraction (it joins the engine spec), Fact or Fiction → Aetherize, Mana Confluence/City of Brass → basics. The
  main risk is dying to go-wide boards, not engine speed.
- **Revision 3 (pilot loss diagnosis):** we lose when another board outgrows the table while we hold no sweeper.
  Added Storm's Wrath, Blasphemous Act, Aetherspouts and Decree of Pain; cut Fiery Confluence, Shimmerwing Chimera,
  Swiftfoot Boots and Izzet Signet. New engine block "Board answer held" (by 7).
