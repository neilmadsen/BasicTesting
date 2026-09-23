# Muldrotha, the Gravetide: Gravetide Value (Bracket 3)

The benchmark build: the crowd's self-mill, ETB-creature and reanimation plan, built
with a proxy mana base and with non-staples only where they beat the staple they
replace. List: `deck.txt`. Print list: `proxies.txt`. This is v3, after the critique
round (see the end of this file).

## Plan

**How it wins.** Fill the graveyard early and land Muldrotha on turn 5 or 6. From
then on she replays, each turn, one land, one creature, one enchantment, one
artifact and one planeswalker from the yard. Ashnod's Altar is the free sacrifice
outlet that keeps the loops running: sacrifice a creature for {C}{C} now, recast it
from the yard next turn. The recurring pieces are removal (Chupacabra, Shriekmaw
evoke, Skyfisher Spider, Grist) and card flow (Mulldrifter evoke, Mystic Remora).
The table runs out of answers before we run out of threats.

**The kill** (defined, 2–3 turns once set up):
1. **Jarad, Golgari Lich Lord.** {1}{B}{G}, sacrifice another creature: each
   opponent loses life equal to its power. Colossal Grave-Reaver is 7 to each
   opponent, Grave Titan and Massacre Wurm 6, Doom Whisperer and Dreadhound 6, and
   Emeritus of Woe 5. Muldrotha recasts one sacrificed fatty per turn, and
   reanimation spells (Reanimate, Animate Dead, Necromancy, Bind to Life, Seedship
   Broodtender, Liliana) return more. Grist's −5 adds life loss equal to the
   creature cards in our yard.
2. **Death drains.** Syr Konrad and Dreadhound each drain every opponent for every
   creature that dies or is milled; on self-mill both trigger for each creature
   card milled. Massacre Wurm (one-sided −2/−2, 2 life per dead creature) and
   Night Incarnate (−3/−3 sweep) turn a token board into drain damage.
3. **Board.** Grave Titan, Grave-Reaver and Doom Whisperer beating down, and
   Living Death with a stocked yard as a reset we win.

**Key turns.** T1–2: a ramp one-drop (Birds, Studious First-Year, Sol Ring) or a
mill piece (Stitcher's Supplier, Seedship Broodtender, Satyr Wayfinder, Aftermath
Analyst). T3–4: an engine (Ashnod's Altar, Twilight Diviner, Doc Aurlock, Blossoming
Tortoise, Icetill Explorer), Emeritus of Woe to tutor the missing piece, The One
Ring against an aggressive table, or an early reanimation. T5–6: Muldrotha, ideally
with Lightning Greaves or Siren Stormtamer up. Keep a Spore Frog in the yard as the
standing fog.

**Mulligan.** Keep 3–4 lands with any 1–2 mana play. Keep 2 lands only with Sol
Ring or a mana one-drop. Ship 1-landers, and ship 5+ land hands with no mill or ramp
piece. The deck doesn't need a specific card in the opener: Emeritus of Woe,
Survival and Gravebreaker Lamia find it later.

**Piloting notes.**
- **Against token decks** (Edgar, Pantlaza, Lathril-style), hold Pernicious Deed or
  Toxic Deluge mana instead of tapping out for value. Evoke Night Incarnate
  *before* deploying our own small engines, because it kills them too.
- **Track the lanes.** Put a die on each permanent type you've cast from the yard
  this turn (land, creature, artifact, enchantment, planeswalker). Dual-typed cards
  (Haywire Mite, Solemn, Grist) use whichever lane is free.
- **Underrealm Lich changes every draw.** With Rhystic Study and Remora out, each
  draw is a pick-1-of-3 decision that also mills 2. It also double-pings with
  Konrad and Dreadhound whenever a creature card is milled.
- **Emeritus of Woe's end-step trigger.** Two creature deaths in a turn re-prepare
  it. An evoked Shriekmaw plus its target, or an Ashnod's Altar sacrifice plus
  a Chupacabra kill, is enough. So Woe is a Demonic Tutor every turn while it lives.
- **Rule 0.** Mention the tutor density: Survival, Emeritus of Woe's repeatable
  Demonic Tutor, Gravebreaker Lamia and The One Ring. The deck is fair, but it is
  consistent.

## Key cards and lines

- **Ashnod's Altar + Muldrotha.** Sacrifice anything Muldrotha will recast (Supplier
  mills 3 on death, Broodtender, Chupacabra after its ETB, Solemn draws), take
  {C}{C}, recast next turn. It also answers exile and theft effects and turns on
  Kaya's Ghostform on demand.
- **Jarad + Ashnod's Altar + fatties.** Jarad is the kill; the Altar is the mana.
  Reanimate a Grave-Reaver, throw it at Jarad (7 to each opponent), and recast it
  from the yard next turn.
- **Emeritus of Woe.** It enters prepared, so a cast (from hand or by Muldrotha
  after it died) gives a Demonic Tutor for {1}{B}. It becomes prepared again at our
  end step if two or more creatures died that turn. The Demonic Tutor copy is cast
  from nowhere, so Doc Aurlock, Lamia and similar cost reducers don't apply to it.
- **Emeritus of Ideation.** A 5/5 flying ward 2 that enters prepared: Ancestral
  Recall for {U}. It rarely dies, so it's not a Muldrotha loop. It re-prepares on
  attack by exiling 8 yard cards, which is strong but shrinks Jarad and Grist's −5,
  so use it only when the yard is deep.
- **Muldrotha + Doc Aurlock (+ Gravebreaker Lamia).** Yard casts cost 2 (3) less.
  Evoked Mulldrifter costs {U}, Overlord of the Balemurk's impending costs {B}, and
  Chupacabra costs {B}{B}.
- **Overlords through the enchantment lane.** Casting an Overlord for its impending
  cost from the yard is legal. It then sits as a non-creature enchantment for 4–5
  turns, so it's one yard cast per trip back to the graveyard, not a loop.
  Balemurk: mill 4 and regrow a creature. Hauntwoods: a land. Twilight Diviner
  can't copy an impending Overlord, because it isn't a creature.
- **Muldrotha + evoke creatures (Wistfulness, Mulldrifter, Shriekmaw, Night
  Incarnate).** Evoke from the yard each turn. Wistfulness paid with GG exiles an
  artifact or enchantment; paid with UU it draws 2 and discards 1.
- **Twilight Diviner.** Once per turn, a token copy of a creature cast or reanimated
  from the yard: a second Chupacabra, Mulldrifter or Grave Titan. Whether a token
  copy of a prepared creature can cast the copied spell is unverified, so don't
  plan on two Demonic Tutors from one Woe.
- **Mystic Remora / Spore Frog / Seal of Primordium / Pernicious Deed loops.** Let
  it die or sacrifice it, then recast it with Muldrotha.
- **Land lane.** Fetchlands, horizon lands (Waterlogged Grove, Nurturing Peatland
  sacrifice to draw), Takenuma (channel regrowth), Boseiju and Otawara (channel
  removal) and Bojuka Bog get replayed from the yard. Jarad returns itself by
  sacrificing a Swamp and a Forest, and Muldrotha replays one of those lands.

## Gems

None of these are on Muldrotha's EDHREC B3 page (2,567 decks).

- **Emeritus of Woe // Demonic Tutor.** A 5/4 for 4 that tutors on arrival, again
  at any end step after two creature deaths, and again each time Muldrotha recasts
  it. It's not a Game Changer. It beats Entomb or Buried Alive in the tutor slot
  because it repeats.
- **Emeritus of Ideation // Ancestral Recall.** A 5/5 flyer with ward 2 that draws 3
  for {U}. It beats Mulldrifter in the evasive-threat role; Mulldrifter stays as the
  cheap evoke loop.
- **Studious First-Year // Rampant Growth.** A one-drop that becomes Rampant Growth
  on turn 2, and again on every recast. It beats Wood Elves and Farhaven Elf on
  curve.
- **Vastlands Scavenger // Bind to Life.** A 4/4 deathtouch for 3, plus a 5-mana
  instant that mills 7 and puts a creature from among them into play. Self-mill and
  reanimation in one card; more than Satyr Wayfinder or Grisly Salvage.
- **Seedship Broodtender.** Mills 3 on ETB like Stitcher's Supplier, later sacrifices
  itself to reanimate, and Muldrotha recasts it: a 2-drop reanimation engine.
- **Blossoming Tortoise.** Mills 3 and puts a land from the yard into play on ETB and
  on every attack. Ramp plus self-mill, where Sakura-Tribe Elder only ramps.
- **Overlord of the Balemurk / Overlord of the Hauntwoods.** A 2- or 3-mana impending
  cast from hand or the yard, through the enchantment lane the crowd underuses:
  mill 4 and regrow a creature, or make a land. Each becomes a 5/5 or 6/5 later.
- **Wistfulness.** Hybrid evoke: a 2-mana Disenchant or a 2-mana draw 2 / discard 1,
  castable from the yard. Hardcast, it does both on a 6/5. More flexible than
  Reclamation Sage.
- **Doom Whisperer.** A 6/6 flying trample for 5 that fills our own yard on demand;
  a better threat than Lord of Extinction at the slot. It's also 6 power for Jarad.
- **Dreadhound.** A second Syr Konrad on a 6/6 body that mills 3 on ETB. Two drain
  engines make "mill and drain" a real finisher.
- **Skyfisher Spider.** Sacrifice a Supplier or Frog to Vindicate on ETB, and repeat
  it with Muldrotha. Ravenous Chupacabra only hits creatures.
- **Night Incarnate.** Evoke for 4 for a −3/−3 sweep against token decks, which is
  what the B3 field plays (see Testing), and repeat it with Muldrotha. Muldrotha and
  our 6/6s survive; our small creatures don't, so sequence it first.

Staples kept because they're simply the best card for the slot: Sakura-Tribe Elder,
Eternal Witness, Kaya's Ghostform, Animate Dead, Spore Frog, Gravebreaker Lamia,
Seal of Primordium, Haywire Mite, Mulldrifter, Chupacabra, Shriekmaw, Pernicious
Deed, Toxic Deluge, Syr Konrad, The Gitrog Monster, Twilight Diviner, Doc Aurlock,
Ashnod's Altar, Jarad.

## Testing

SIM_SECTION_PLACEHOLDER

## Bracket

`./edh validate deck.txt --bracket 3` → **PASS**.
- **Game Changers: 3 of 3** (Rhystic Study, Survival of the Fittest, The One Ring).
- **Combos: none found.** Commander Spellbook reports no combos in the 99. Its
  deck-level "Powerful (≈bracket 3+)" tag is a generic estimate, not a combo flag.
  Ashnod's Altar and Jarad are sacrifice outlets, but no infinite loop exists in the
  list: nothing untaps, persists or returns itself for free. Muldrotha allows one
  creature cast from the yard per turn, and Kaya's Ghostform and Animate Dead are
  one-shots.
- **Kill speed.** The Jarad close is a turn 7–9 affair in practice. It needs
  Muldrotha or reanimation plus 4+ mana of activations over 2–3 turns, which fits
  B3.
- **MLD: none.** Strip Mine and Wasteland were left out deliberately, because
  Muldrotha replaying one every turn is a land-destruction lock.
- **Extra turns: none.**
- **Spirit check.** The fastest scary line is Reanimate on a milled Grave-Reaver on
  turn 2–3. It needs the fatty milled first, and the creature doesn't win on its
  own. There's no Entomb or Buried Alive, per the brief. The deck is tutor-dense,
  so mention it at Rule 0.

## Swaps considered (flex slots, for the user's taste)

- **Secrets of the Dead** (cut in v3 for The One Ring). It draws on every
  Muldrotha cast, but draws nothing before she lands.
- **Kheru Goldkeeper** (cut in v3 for Jarad). Treasure off every yard cast, but no
  kill.
- **Emeritus of Abundance** (cut in v3 for Ashnod's Altar). A Regrowth on a body
  that repeats Eternal Witness's job.
- **More artifact-lane removal.** Executioner's Capsule (3 mana per loop, nonblack
  only), Anchovy & Banana Pizza (cut in v2), or Seal of Doom for the enchantment
  lane.
- **Sheoldred, Whispering One / Sludge Titan / Chupacabra Echo.** All good. They
  missed on curve.
- **Overlord of the Floodpits.** The third Overlord: impending {1}{U}{U}, draw 2 and
  discard 1. A swap for Underrealm Lich if you want less decision load.
- **Altar of Dementia.** The crowd's outlet (40%). Ashnod's Altar was chosen
  because mana matters more here than milling opponents; also Forge can't play
  Altar of Dementia.
- **Utility lands: Port of Karfell, Memorial to Folly.** Muldrotha replays them, but
  they enter tapped. Swap for Exotic Orchard if the table is slow.
- **Rejected on purpose:** Entomb and Buried Alive (brief); Strip Mine loops (MLD
  spirit); Tithing Blade (never returns to the yard, so it can't loop); Hermit
  Druid (combo territory); the dozen "mill 3 on ETB" bears Jev ranks highly
  (Necromancer's Assistant, Armored Skaab, Crow of Dark Tidings). Each does less
  than Seedship Broodtender or Satyr Wayfinder.

## Critique round (v2 → v3)

A deck-critic review returned "not as is; yes with three swaps and corrected
notes." I agreed with all three swaps and all the rules corrections:

- **−Emeritus of Abundance, +Ashnod's Altar.** v2 had no free sacrifice outlet, so
  the recast loops only ran when opponents killed our creatures. The Altar makes
  the engine proactive and fills the nearly empty artifact lane. My v2 note that
  dismissed Altar of Dementia as "not affecting the board" missed that job.
- **−Kheru Goldkeeper, +Jarad, Golgari Lich Lord.** v2 won by attacking around
  turn 10 or later with no defined kill. Jarad throws recurring fatties at each
  opponent.
- **−Secrets of the Dead, +The One Ring** (third Game Changer). My v2 argument that
  a third Game Changer would feel like B4 didn't hold, because Woe and Ideation
  already give repeatable Demonic Tutor and Ancestral Recall outside the count. The
  Ring blanks a turn of the combat damage that killed us in the sim, then draws.
- **Rules corrections** (in deck.txt notes and above):
  - Emeritus of Woe re-prepares at our end step after 2+ creature deaths, not only
    when recast.
  - Emeritus of Ideation isn't a Muldrotha loop.
  - Twilight Diviner copying a prepared spell is unverified.
  - Overlords are one impending cast per trip to the yard, and Diviner can't copy
    them.
  - Night Incarnate also sweeps our own small creatures.
  - The prepared-spell copies are cast from nowhere, so yard cost reducers don't
    apply to them.

## Scouting record

In `candidates/`:
- `edhrec-b3*.txt`: the crowd baseline.
- `jev-rank-full.*`: the live Jev rank.
- `jev-rank-lexical.json`: a run before the key existed. Ignore it.
- `jev-grep-*.json`: noncreature removal permanents, and utility lands that loop
  with Muldrotha.
- `scry-*.txt`: pools for prepared, impending, evoke and ETB-removal cards.
- `deck-v1-simmed.txt`: the list the first sim ran.
