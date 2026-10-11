"""Offline tests for the deck-builder tools: pool browsing, the engine goldfish, and audit parsing.

Model-calling paths (claims and gems judging) aren't exercised here; their parsing and selection are.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edhkit import deckaudit, engine  # noqa: E402
from edhkit.deck import Deck  # noqa: E402
from edhkit.paths import CARDS_DB  # noqa: E402

HAS_DB = CARDS_DB.exists()

BRIEF = """# Test
```engine
name: Upkeep engine
by: 6
commander
2 of: regex:at the beginning of your upkeep  # comment allowed
held 1 of: tag:counterspell; Counterspell
tutors: Mystical Tutor
```
Some prose.
```engine
1 of: Phyrexian Arena; type:Saga
```
"""


class EngineSpec(unittest.TestCase):
    def test_parse_blocks(self):
        specs = engine.parse(BRIEF)
        self.assertEqual(len(specs), 2)
        e = specs[0]
        self.assertEqual((e.name, e.by, e.commander), ("Upkeep engine", 6, True))
        self.assertEqual([(r.n, r.held) for r in e.reqs], [(2, False), (1, True)])
        self.assertEqual(e.reqs[1].terms, ["tag:counterspell", "Counterspell"])
        self.assertEqual(e.tutors, ["Mystical Tutor"])
        self.assertEqual(specs[1].name, "engine 2")

    def test_bad_line_raises(self):
        with self.assertRaises(ValueError):
            engine.parse("```engine\nthree of: x\n```")


@unittest.skipUnless(HAS_DB, "card DB not built")
class EngineSim(unittest.TestCase):
    def deck(self, extra: str) -> Deck:
        from edhkit.cards import CardDB
        d = Deck.parse("# Commander\n1 Obeka, Splitter of Seconds\n# Deck\n" + extra
                       + "12 Island\n12 Swamp\n12 Mountain\n")
        d.resolve(CardDB())
        return d

    def test_more_pieces_assemble_sooner(self):
        filler = "".join(f"1 {n}\n" for n in ["Opt", "Consider", "Lightning Bolt", "Duress", "Shock"])
        thin = self.deck("1 Phyrexian Arena\n" + filler)
        thick = self.deck("1 Phyrexian Arena\n1 Court of Ire\n1 Court of Vantress\n1 Court of Locthwain\n" + filler)
        spec = engine.parse("```engine\nby: 6\ncommander\n1 of: regex:at the beginning of your upkeep\n```")[0]
        a = engine.simulate(thin, spec, trials=1500, seed=3)
        b = engine.simulate(thick, spec, trials=1500, seed=3)
        self.assertGreater(b.online_by[8], a.online_by[8])
        self.assertIn("commander", b.bottleneck)

    def test_held_cards_are_not_spent(self):
        d = self.deck("1 Counterspell\n1 Opt\n")
        spec = engine.parse("```engine\n1 of: type:Instant\nheld 1 of: Counterspell\n```")[0]
        r = engine.simulate(d, spec, trials=800, seed=1)
        # Counterspell may never be cast to satisfy the instant requirement, so Opt alone must do it
        self.assertLessEqual(r.online_by[10], 1.0)
        self.assertGreater(r.online_by[10], 0.0)

    def test_warns_when_deck_cannot_meet_spec(self):
        d = self.deck("1 Opt\n")
        spec = engine.parse("```engine\n2 of: Court of Ire; Court of Vantress\ntutors: Demonic Tutor\n```")[0]
        warns = engine.resolve(spec, d)
        self.assertTrue(any("needs 2" in w for w in warns))
        self.assertTrue(any("Demonic Tutor" in w for w in warns))


@unittest.skipUnless(HAS_DB, "card DB not built")
class AuditParsing(unittest.TestCase):
    def setUp(self):
        from edhkit.cards import CardDB
        self.db = CardDB()
        self.d = Deck.parse(
            "# Commander\n1 Obeka, Splitter of Seconds\n# Deck\n"
            "1 Court of Ire  # GEM vs Phyrexian Arena — upkeep payoff: Obeka's extra upkeeps each deal 2\n"
            "1 Phyrexian Arena  # draw: one card per upkeep, so Obeka turns it into several\n"
            "1 Sol Ring  # GEM ramp: no staple named\n"
            "30 Island\n")
        self.d.resolve(self.db)

    def test_gem_entries_read_vs(self):
        gems = {e.name: (staple, role) for e, staple, role in deckaudit.gem_entries(self.d)}
        self.assertEqual(gems["Court of Ire"], ("Phyrexian Arena", "upkeep payoff"))
        self.assertEqual(gems["Sol Ring"][0], None)

    def test_gems_flag_undisplaced_staple_without_calling_a_model(self):
        rows = deckaudit.audit_gems(self.d, "brief", self.db)  # no judgeable pairs -> no model call
        res = {r["gem"]: r["result"] for r in rows}
        self.assertEqual(res["Court of Ire"], "staple is also in the deck (not displaced)")
        self.assertEqual(res["Sol Ring"], "no staple named")

    def test_claim_items_link_named_cards(self):
        notes = "- Obeka's extra upkeeps let Phyrexian Arena and Court of Ire trigger several times a turn.\n- Short.\n"
        items = deckaudit.claim_items(self.d, notes)
        arena = next(i for i in items if i["card"] == "Phyrexian Arena")
        self.assertIn("Obeka, Splitter of Seconds", arena["cards"])  # 'Obeka' short name resolves
        note_items = [i for i in items if i["source"] == "notes.md"]
        self.assertEqual(len(note_items), 1)
        self.assertGreaterEqual(len(note_items[0]["cards"]), 2)

    def test_omissions_with_fake_edhrec(self):
        from unittest import mock
        page = {"cards": {"Sol Ring": {"inclusion": 0.9}, "Arcane Signet": {"inclusion": 0.88},
                          "As Foretold": {"inclusion": 0.83}, "Island": {"inclusion": 0.98},
                          "Court of Vantress": {"inclusion": 0.2}}}
        with mock.patch("edhkit.edhrec.commander_page", return_value=page):
            rows = deckaudit.omissions(self.d, "As Foretold is out: no suspend here.", 3)
        got = {r["name"]: r["addressed"] for r in rows}
        self.assertEqual(got, {"Arcane Signet": False, "As Foretold": True})


@unittest.skipUnless(HAS_DB, "card DB not built")
class PoolBrowse(unittest.TestCase):
    def test_pages_groups_and_inclusion(self):
        from edhkit import pool
        from edhkit.cards import CardDB
        from edhkit.search import Filters, ci_from_arg
        db = CardDB()
        f = Filters(ci_mask=ci_from_arg(db, "Obeka, Splitter of Seconds"), regex="at the beginning of your upkeep",
                    lands="exclude")
        cards = pool.select(db, f, not_regex="cumulative upkeep")
        self.assertGreater(len(cards), 100)
        self.assertFalse(any("Cumulative upkeep" in c.text for c in cards))
        out = pool.browse(cards, page=2, per_page=20, incl={"Phyrexian Arena": 0.3}, num_decks=100,
                          deck_names={"Phyrexian Arena"})
        self.assertIn("page 2/", out)
        self.assertIn("## ", out)
        full = pool.browse(cards, page=1, per_page=len(cards), incl={"Phyrexian Arena": 0.3}, num_decks=100,
                           deck_names={"Phyrexian Arena"})
        self.assertIn("30% of decks", full)
        self.assertIn("IN DECK", full)
        self.assertIn("unlisted", full)


if __name__ == "__main__":
    unittest.main()
