"""Offline tests: parsing, log parsing, Jev batching (with a fake transport), bracket basics.

Run with `python3 -m unittest discover tests`. Tests that need the card DB skip
when it hasn't been built.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edhkit import forge, jev  # noqa: E402
from edhkit.deck import Deck  # noqa: E402
from edhkit.paths import CARDS_DB  # noqa: E402

HAS_DB = CARDS_DB.exists()


class DeckParsing(unittest.TestCase):
    def test_canonical_with_notes(self):
        d = Deck.parse("# Commander\n1 Meren of Clan Nel Toth\n\n# Creatures (2)\n1 Viscera Seer  # sac outlet\n2 Swamp\n")
        self.assertEqual([e.name for e in d.commanders], ["Meren of Clan Nel Toth"])
        self.assertEqual(d.main[0].note, "sac outlet")
        self.assertEqual(d.size(), 4)

    def test_moxfield_export_style(self):
        d = Deck.parse("Commander\n1 Atraxa, Praetors' Voice (CM2) 10\n\nDeck\n1x Sol Ring (CMM) 400 *F*\n1 Fire // Ice\n")
        self.assertEqual(d.commanders[0].name, "Atraxa, Praetors' Voice")
        self.assertEqual([e.name for e in d.main], ["Sol Ring", "Fire // Ice"])

    def test_forge_dck(self):
        d = Deck.parse("[metadata]\nName=Test\n[Commander]\n1 Nissa, Vital Force|KLD\n[Main]\n7 Forest|KLD|1\n")
        self.assertEqual(d.title, "Test")
        self.assertEqual(d.commanders[0].name, "Nissa, Vital Force")
        self.assertEqual(d.main[0].qty, 7)

    def test_cmdr_marker(self):
        d = Deck.parse("1 Sol Ring\n1 Krenko, Mob Boss *CMDR*\n")
        self.assertEqual(d.commanders[0].name, "Krenko, Mob Boss")


SAMPLE_LOG = """Simulation mode
Mulligan: Ai(1)-P1 has kept a hand of 7 cards
Mulligan: Ai(2)-P2 has kept a hand of 7 cards
Turn: Turn 1 (Ai(1)-P1)
Phase: Ai(1)-P1's Untap step
Land: Ai(1)-P1 played Forest (26)
Turn: Turn 2 (Ai(2)-P2)
Add To Stack: Ai(2)-P2 cast Sol Ring
Turn: Turn 3 (Ai(1)-P1)
Add To Stack: Ai(1)-P1 cast Llanowar Elves targeting [nothing]
Life: Life: Ai(2)-P2 40 > 0
Game Outcome: Turn 2
Game Outcome: Ai(2)-P2 has lost because life total reached 0
Game Outcome: Ai(1)-P1 has won because all opponents have lost
Game Result: Game 1 ended in 1000 ms. Ai(1)-P1 has won!
Turn: Turn 1 (Ai(2)-P2)
Stopping slow match as draw
Game Result: Game 2 ended in a Draw! Took 5 ms.
Turn: Turn 1 (Ai(1)-P1)
Game Outcome: Ai(1)-P1 has won because all opponents have lost
Game Outcome: Ai(2)-P2 has won because all opponents have lost
Game Result: Game 3 ended in 208963 ms. Ai(2)-P2 has won!
"""


class ForgeLogParsing(unittest.TestCase):
    def test_parse(self):
        games = forge.parse_games(SAMPLE_LOG)
        self.assertEqual(len(games), 3)
        self.assertTrue(games[2][0].timeout)  # everyone "won" → draw
        self.assertIsNone(games[2][0].winner)
        g, lines = games[0]
        self.assertEqual(g.winner, "P1")
        self.assertEqual(g.lost_reason["P2"], "life total reached 0")
        self.assertEqual(g.casts["P1"], [("Llanowar Elves", 3)])
        self.assertEqual(g.kept["P1"], 7)
        self.assertFalse(any(line.startswith("Phase:") for line in lines))
        self.assertTrue(games[1][0].timeout)
        self.assertIsNone(games[1][0].winner)

    def test_graveyard_usage(self):
        lines = [
            "Land: Ai(1)-P1 played Forest (10)",
            "Land: Ai(2)-P2 played Plains (50)",
            "Ai(1)-P1 milled Seal of Doom (12), Swamp (13) and Mulldrifter (14).",
            "Zone Change: Executioner's Capsule (15) was put into Graveyard from Battlefield.",
            "Zone Change: Muldrotha, the Gravetide (9) was put into Graveyard from Battlefield.",
            "Zone Change: Sol Ring (55) was put into Graveyard from Battlefield.",  # opponent's id block
            "Add To Stack: Ai(1)-P1 cast Executioner's Capsule",
            "Add To Stack: Ai(1)-P1 cast Seal of Doom",
            "Add To Stack: Ai(1)-P1 cast Muldrotha, the Gravetide",
            "Add To Stack: Ai(1)-P1 cast Sol Ring",
            "Land: Ai(1)-P1 played Swamp (13)",
        ]
        gu = forge.graveyard_usage(lines, "P1", {"Muldrotha, the Gravetide"})
        self.assertEqual(gu["spells"], 2)
        self.assertEqual(gu["lands"], 1)
        self.assertNotIn("Sol Ring", gu["cards"])

    def test_wilson(self):
        lo, hi = forge.wilson(10, 40)
        self.assertTrue(0.12 < lo < 0.15 and 0.39 < hi < 0.42)


class FakeJev(jev.JevProvider):
    def __init__(self):
        super().__init__("fake")
        self.cache = type("C", (), {"key": staticmethod(lambda s, q: None), "get": lambda self, k: None,
                                    "put_many": lambda self, items: None})()
        self.calls = []

    def _post(self, state, questions):
        self.calls.append(len(questions))
        out = {}
        for qid, q in questions.items():
            name = q["instructions"]["card"]["name"]
            if q["type"] == "score":
                out[qid] = {"type": "score", "score": 3.5 if "Blood" in name else 0.5, "confidence": 0.9,
                            "probabilities": {}}
            else:
                out[qid] = {"type": "noul", "noul": 0.9 if "Blood" in name else 0.1}
        return out


@unittest.skipUnless(HAS_DB, "card DB not built")
class JevBatching(unittest.TestCase):
    def test_rank_and_grep(self):
        from edhkit.cards import CardDB
        db = CardDB()
        cards = [db.require(n) for n in ("Blood Artist", "Sol Ring", "Llanowar Elves")] * 60
        p = FakeJev()
        js, usage = jev.rank(cards, "aristocrats", provider=p)
        self.assertEqual(js[0].card.name, "Blood Artist")
        self.assertGreater(len(p.calls), 1)  # 180 questions → more than one request
        self.assertLessEqual(max(p.calls), jev.MAX_QUESTIONS_PER_REQUEST)
        js, _ = jev.grep(cards, "drains on death", provider=FakeJev())
        self.assertAlmostEqual(js[0].value, 0.9)


@unittest.skipUnless(HAS_DB, "card DB not built")
class Brackets(unittest.TestCase):
    def test_offline_checks(self):
        from edhkit import brackets
        from edhkit.cards import CardDB
        db = CardDB()
        main = "\n".join(["1 Sol Ring", "1 Armageddon", "1 Time Warp", "1 Demonic Tutor", "1 Rhystic Study",
                          "1 Cyclonic Rift", "1 Smothering Tithe", "2 Arcane Signet"] + ["88 Island"])
        d = Deck.parse(f"# Commander\n1 Hanna, Ship's Navigator\n# Deck\n{main}\n")
        r = brackets.validate(d, 3, db, use_spellbook=False)
        self.assertTrue(any("singleton" in e for e in r.errors))
        self.assertTrue(any("Game Changers" in v for v in r.violations))
        self.assertTrue(any("mass land denial" in v for v in r.violations))
        self.assertTrue(any("Demonic Tutor" in x for x in r.game_changers))


class PilotLogic(unittest.TestCase):
    def _state(self, my_board, opp_board, my_life=40, opp_life=40, turn=5, active="P1"):
        return {"turn": turn, "me": "P1", "active": active, "my_command_zone": [],
                "players": [{"name": "P1", "is_me": True, "life": my_life, "battlefield": my_board},
                            {"name": "P2", "is_me": False, "life": opp_life, "battlefield": opp_board}]}

    def test_changes_since_detects_wipe_and_life_swing(self):
        from edhkit.pilot import changes_since
        before = self._state(["Muldrotha, the Gravetide 6/6", "Seal of Doom", "Zombie 2/2 [token] x3", "Forest [land] x4"],
                             ["Elf 1/1 [token] x6"])
        after = self._state(["Forest [land] x4"], ["Elf 1/1 [token] x6"], my_life=30)
        notes = changes_since(before, after)
        self.assertTrue(any("nonland permanents 5→0" in n for n in notes), notes)
        self.assertTrue(any("life 40→30" in n for n in notes), notes)
        self.assertTrue(any("Muldrotha" in n for n in notes), notes)
        self.assertEqual(changes_since(before, before), [])

    def test_ask_gates_and_escalates(self):
        from edhkit import pilot as P

        class FakeProvider:
            usage = {"input_tokens": 0}

            def __init__(self):
                self.calls = 0

            def evaluate(self, state, questions):
                self.calls += 1
                out = {}
                for qid, q in questions.items():
                    if q["type"] == "noul":
                        out[qid] = {"noul": 0.9}
                    elif qid == "close":   # slight preference for non-default → gated back to default
                        out[qid] = {"choice": "b", "probabilities": {"a": 0.45, "b": 0.55}}
                    else:                  # clear preference → overrule
                        out[qid] = {"choice": "b", "probabilities": {"a": 0.1, "b": 0.9}}
                return out

        p = P.Pilot.__new__(P.Pilot)
        P.Pilot.__init__.__globals__  # keep linters quiet
        p.plan, p.strategist, p.model, p.gate, p.sync, p.escalate = "plan", "claude-cli", "m", 0.15, True, True
        p.provider, p.log_dir = FakeProvider(), None
        import threading
        from collections import defaultdict
        p._log_lock, p._glock, p._games, p._server = threading.Lock(), threading.Lock(), {}, None
        p.stats = {"errors": 0, "latency_ms": [], "strategist_calls": 0, "strategist_ms": [], "strategist_errors": 0,
                   "escalations": 0, "escalation_checks": 0,
                   "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}
        refreshed = []
        p._refresh = lambda game, state, reason: (refreshed.append(reason),
                                                  p._game(game).update(memo="new memo", memo_state=state, pending=False))
        before = self._state(["Seal of Doom", "Zombie 2/2 [token] x4"], [], turn=5, active="P1")
        g = p._game("g1")
        g.update(memo="old memo", memo_state=before, turn=5)
        after = self._state([], [], turn=6, active="P2")
        req = {"game": "g1", "kind": "block", "state": after, "questions": [
            {"id": "clear", "default": "a", "prompt": "?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            {"id": "close", "default": "a", "prompt": "?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]}]}
        out = p.ask(req)["answers"]
        self.assertEqual(out["clear"], "b")
        self.assertEqual(out["close"], "a")
        self.assertEqual(p.stats["escalations"], 1)
        self.assertTrue(refreshed and refreshed[0].startswith("executor escalation"))
        self.assertEqual(p.provider.calls, 2)  # asked, escalated, re-asked under the new memo
        p.ask(req)  # same turn: no second escalation
        self.assertEqual(p.stats["escalations"], 1)

        # action + speculative targets: only the taken action's target question counts
        p.stats["by_kind"].clear()
        opts = [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]
        req = {"game": "g1", "kind": "action", "state": after, "questions": [
            {"id": "action", "default": "a", "prompt": "?", "options": opts},
            {"id": "tgt_a", "default": "a", "prompt": "?", "options": opts},
            {"id": "tgt_b", "default": "a", "prompt": "?", "options": opts}]}
        out = p.ask(req)["answers"]
        self.assertEqual(out["action"], "b")
        ks = p.stats["by_kind"]["action"]
        self.assertEqual((ks["questions"], ks["overrules"]), (2, 2))  # action + tgt_b; tgt_a unused


if __name__ == "__main__":
    unittest.main()
