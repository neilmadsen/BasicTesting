# Bug ledger: the Vivi pilot

Every defect found in the Vivi bug hunt, grouped by root cause. How each was found:
- `bugscan`: log invariants, no model calls;
- `scenario`: a Forge board replayed in seconds;
- `turn-audit`: a model reviews the turns that matter;
- by hand.

Layers:
- **engine:** Forge's rules or AI.
- **harness:** decisions the pilot never sees, or answers not applied as chosen.
- **tagging:** the memo's plan reaching the executor.
- **executor:** Jev's choices.
- **strategist:** the memo itself.

## Fixed

| # | layer | defect | found | fix |
|---|---|---|---|---|
| 1 | tagging | a card named by nickname went untagged; a fallback was tagged as the plan | hand | 29c51a4 |
| 2 | harness | a hold hid the plays that would spend the held mana | hand | be0143d |
| 3 | harness | transient API errors not retried, so Forge passed a whole main phase | hand | ac1b33e |
| 4 | harness | Vivi's mana was never offered, so overload and big X were impossible | hand | 530075c |
| 5 | harness | Vivi's once-per-turn mana ability was usable repeatedly | hand | 530075c |
| 6 | tagging | commentary was tagged as a plan; a hold was tagged as a play | hand | 61d2d5d |
| 7 | tagging | a play after a mana clause went untagged ("for {C}, then cast X"), 22 plays in 119 memos | hand | ce6ab11 |
| 8 | harness | counterspells targeted the spell's card, not the spell, and did nothing (4 of 6) | hand, bugscan | cb08b20 |
| 9 | engine | Forge's AI chose nothing for a Curiosity Aura on a 0-power creature, stranding Ophidian Eye and Sigil of Sleep cast on Vivi (0 triggers in 24) | bugscan, scenario | cb08b20 |
| 10 | harness | modal trigger targets (Hullbreaker Horror) were never asked | hand, turn-audit | ec6da98 |
| 11 | executor | Vivi's mana was made with nothing to spend it on | bugscan | ec6da98 |
| 12 | executor | memo-ordered attacks needed the big margin; a blanket "No attacks" reached no attacker | hand | ec6da98 |
| 13 | executor | the equipment cap of one blocked a move and a move back | hand | ec6da98 |
| 14 | tagging | Brainstorm put-backs and discards had no memo tags | hand, turn-audit | ec6da98 |
| 15 | harness | soulbond pairing and Aura attachments missing from the state | hand | ec6da98 |
| 16 | strategist | draw triggers not counted against the library (decked with a won game); a keyword rule read backwards (the Ring) | hand, turn-audit | ec6da98 (checklist 4d) |

## Open

| # | layer | defect | found | notes |
|---|---|---|---|---|
| A | tagging | later steps of a scripted chain stay tagged after an earlier step fails | turn-audit | tie step tags to their preconditions, or escalate when a planned card isn't played |
| B | harness | Cascade Bluffs and other filter lands are never used (AI-blind) | hand | offer them as explicit mana actions |
| C | harness | Vivi's colour split isn't sized to the most expensive castable spell | hand | |
| D | harness | no priority with our own spell on the stack | hand | only matters with instant-speed follow-ups |
| E | harness | effect discards (Frantic Search) are routed to Forge | hand | check `chooseCardsToDiscardFrom` coverage |
