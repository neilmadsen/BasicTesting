---
name: brackets
description: Commander Brackets rules (WotC beta, Feb 2026 update) — Game Changers, mass land denial, extra turns, two-card combos — and how to judge the grey areas. Use when validating a deck, choosing cards near a bracket line, or answering bracket questions.
---

# Commander Brackets (as of the Feb 9, 2026 update)

| # | Name | Game Changers | Mass land denial | Extra turns | Two-card combos | Feel |
|---|---|---|---|---|---|---|
| 1 | Exhibition | 0 | no | no | no | theme first; games long |
| 2 | Core | 0 | no | a Time Warp or two, no chaining | no intentional infinites | precon level |
| 3 | Upgraded | ≤3 | no | low count, no chaining/looping | no *early-game* two-card infinites; a combo that wins around turn 6+ is fine | strong synergy, efficient interaction |
| 4 | Optimized | any | yes | yes | yes | lethal, consistent, fast |
| 5 | cEDH | any | yes | yes | yes | metagame-driven, maximal |

Tutor limits were removed in October 2025. There are 53 Game Changers (Farewell
and Biorhythm added in Feb 2026; Lutri stays off because it's unbanned but not
powerful). The DB's `game_changer` flag comes from Scryfall, so `./edh cards update`
picks up list changes. Check the current state at magic.wizards.com if a card
seems borderline.

## Running the check
```bash
./edh validate deck.txt --bracket 3          # human report; exit code 2 on FAIL
./edh validate deck.txt --bracket 3 --json   # structured
```
It checks legality (size, singleton incl. "any number" cards, color identity,
banlist, commander/partner validity), the Game Changer count, mass land denial and
extra turns (from Commander Spellbook's flags plus a local list), and combos
present in the 99 (Commander Spellbook `/estimate-bracket`).

## Judgement calls (the REVIEW section)

- **Combos at B3.** The line is *early-game* two-card infinites. A cheap pair
  like Thassa's Oracle + Demonic Consultation, or Dramatic Reversal +
  Isochron Scepter, is out. A 12-mana three-card line that happens incidentally
  is fine. If a combo is present, say in notes.md whether it's the plan or an
  accident, and roughly the earliest realistic turn.
- **Spellbook's MLD flag** catches ultimates and rare modes (e.g. planeswalker
  -9s). Those are not land-denial plans. Genuine MLD (Armageddon, Ruination,
  Blood Moon, Winter Orb) is a hard no below B4.
- **Extra turns.** Count the cards *and* the recursion. Two Time Warps plus
  Archaeomancer plus Mnemonic Wall is a chain.
- **Spirit of the bracket.** The rules are floors, not targets. A B3 deck with
  three Game Changers, perfect tutors and a turn-5 kill is B4 in practice. When a
  deck is sharper than its bracket's feel, say so, or detune it.
- **Commander Spellbook's deck-level tag** (e.g. "Ruthless") comes from combos
  alone and is often loud for B3 decks with incidental infinites. It's
  information, not a verdict.
