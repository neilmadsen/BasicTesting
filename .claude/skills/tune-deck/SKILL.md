---
name: tune-deck
description: Improve an existing Commander decklist the user provides (pasted text, Moxfield/Archidekt export, or file) — diagnose it, find upgrades and hidden gems for its plan, respect its identity and bracket, and test changes. Use for "improve/upgrade/fix my deck" requests.
---

# Tune an existing deck

The user's deck has an identity. Improve it on its own terms; don't replace it
with the deck you'd have built. If you think the plan itself is the problem, say
so and offer a separate build via `brew`.

1. **Ingest.** Save to `decks/<slug>/<name>/original.txt`. If the list has no
   commander header, pass `--commander "Name"`:
   `./edh deck original.txt --commander "Name"` (prints the normalized list).
   Fix unknown names with the suggestions. Copy it to `deck.txt` and work there.
2. **Diagnose.**
   `./edh validate deck.txt --bracket N`, `./edh analyze deck.txt`, `./edh hands deck.txt`.
   Then read the list and write the plan as you understand it in `brief.md`. Ask the
   user one question if the plan is genuinely ambiguous.
3. **Find the weak slots.** Weak slots are: cards that don't serve the plan,
   strictly-worse versions of available cards (with proxies, *everything* is
   available), role gaps from `analyze`, and mana problems from the goldfish.
   Score the deck's own cards against the brief:
   `./edh jev rank --brief brief.md --ci "<commander>" --top 400` and note where its
   current cards land.
4. **Scout replacements** with the card-scout funnel, aimed at the weak slots.
5. **Propose swaps as a table** (out → in, reason, gem/staple). Group them into
   "clear upgrades", "plan-sharpening", and "taste calls". Apply the first
   two groups unless the user wants to review first.
6. **Test.** Goldfish before and after. If 8+ cards changed, run
   `./edh compare original.txt deck.txt --bracket N --games 60`.
7. **Deliver** `deck.txt` (annotated), a swap table in `notes.md`, and `proxies.txt`
   for **just the new cards** (the user owns the rest):
   `./edh diff original.txt deck.txt --proxies-out proxies.txt`.
