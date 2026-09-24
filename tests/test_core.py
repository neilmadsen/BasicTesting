"""Offline tests: parsing, log parsing, Jev batching (with a fake transport), bracket basics.

Run with `python3 -m unittest discover tests`. Tests that need the card DB skip
when it hasn't been built.
"""

import sys
import json
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

    def test_changes_since_ignores_taps_and_counters(self):
        from edhkit.pilot import changes_since, parse_entry
        self.assertEqual(parse_entry("Muldrotha, the Gravetide 6/6 (tapped 1)")["name"], "Muldrotha, the Gravetide")
        e = parse_entry("Zombie 2/2 [token] {P1P1=1} x3 (tapped 2)")
        self.assertEqual((e["name"], e["n"], e["token"], e["creature"]), ("Zombie", 3, True, True))
        self.assertEqual(parse_entry("Ratchet Bomb {{CHARGE=2}}")["name"], "Ratchet Bomb")
        before = self._state(["Sol Ring", "Ratchet Bomb {{CHARGE=1}}", "Grist, the Hunger Tide {{LOYALTY=3}}"], [])
        after = self._state(["Sol Ring (tapped 1)", "Ratchet Bomb {{CHARGE=2}}", "Grist, the Hunger Tide {{LOYALTY=4}}"], [])
        self.assertEqual(changes_since(before, after), [])
        before["my_command_zone"] = []
        before["players"][0]["battlefield"].append("Muldrotha, the Gravetide 6/6")
        after["my_command_zone"] = ["Muldrotha, the Gravetide"]
        notes = changes_since(before, after)
        self.assertIn("our commander left the battlefield", notes)
        self.assertTrue(any(n.startswith("we lost: Muldrotha") for n in notes), notes)

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
        p._refresh = lambda game, state, reason, quick=False: (refreshed.append(reason),
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
        p.ask(req)  # same round: no second escalation
        self.assertEqual(p.stats["escalations"], 1)
        req2 = dict(req, state=dict(after, turn=7))
        p.ask(req2)  # an opponent's later turn in the same round: still none
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
        p.stats["by_kind"].clear()
        req["questions"] = req["questions"][:1] + [
            {"id": "x_a", "default": "a", "prompt": "?", "options": opts},
            {"id": "x_b", "default": "a", "prompt": "?", "options": opts}]
        p.ask(req)
        ks = p.stats["by_kind"]["action"]
        self.assertEqual(ks["questions"], 2)  # action + x_b; x_a belongs to an action not taken

    def test_pass_veto_needs_bigger_margin_and_own_sacrifices_are_not_news(self):
        from edhkit import pilot as P
        import threading
        from collections import defaultdict

        class Provider:
            usage = {"input_tokens": 0}
            margin = 0.2

            def evaluate(self, state, questions):
                hi = (1 + self.margin) / 2
                return {"action": {"choice": "pass", "probabilities": {"pass": hi, "o0": 1 - hi}}}

        p = P.Pilot.__new__(P.Pilot)
        p.plan, p.strategist, p.model, p.gate, p.pass_gate, p.sync, p.escalate = "plan", "static", "m", 0.15, 0.35, True, True
        p.provider, p.log_dir = Provider(), None
        p._log_lock, p._glock, p._games, p._server = threading.Lock(), threading.Lock(), {}, None
        p.stats = {"errors": 0, "latency_ms": [], "strategist_calls": 0, "strategist_ms": [], "strategist_errors": 0,
                   "escalations": 0, "escalation_checks": 0,
                   "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}
        mire = "activate Bloodstained Mire (from Battlefield): {T}, Pay 1 life, Sacrifice Bloodstained Mire: Search..."
        st = self._state(["Bloodstained Mire", "Sol Ring"], [], turn=5)
        req = {"game": "g", "kind": "action", "state": st, "questions": [
            {"id": "action", "default": "o0", "prompt": "?",
             "options": [{"id": "o0", "text": mire}, {"id": "pass", "text": "pass"}]}]}
        self.assertEqual(p.ask(req)["answers"]["action"], "o0")   # 0.2 margin: not enough to veto
        self.assertIn("Bloodstained Mire", p._game("g")["ours"])  # we cracked it ourselves
        before = self._state(["Bloodstained Mire", "Sol Ring", "Seal of Doom"], [])
        after = self._state(["Sol Ring"], [])
        notes = P.changes_since(before, after, p._game("g")["ours"])
        self.assertEqual(notes, ["we lost: Seal of Doom"])         # the Mire is not news; the Seal is
        Provider.margin = 0.5
        self.assertEqual(p.ask(req)["answers"]["action"], "pass")  # a clear veto still goes through


class ClaudeCallFailures(unittest.TestCase):
    def test_limit_text_is_a_failure_and_never_becomes_a_memo(self):
        from edhkit import claude_cli, pilot as P
        self.assertTrue(claude_cli.FAILURE.match("You've hit your session limit · resets 6:40pm (UTC)"))
        self.assertTrue(claude_cli.FAILURE.match("API Error: 529 overloaded"))
        self.assertFalse(claude_cli.FAILURE.match("THIS TURN: play Bayou, cast Sol Ring."))
        import threading
        from collections import defaultdict
        p = P.Pilot.__new__(P.Pilot)
        p.plan, p.strategist, p.model, p.version, p.effort, p.verify = "plan", "claude-cli", "m", "v2", "low", None
        p.log_dir = None
        p._log_lock, p._glock, p._games = threading.Lock(), threading.Lock(), {}
        p.stats = {"strategist_calls": 0, "strategist_ms": [], "strategist_errors": 0}
        g = p._game("g")
        g["memo"] = "good old plan"
        orig = claude_cli.run

        def boom(*a, **k):
            raise claude_cli.ClaudeCallFailed("You've hit your session limit")
        claude_cli.run = boom
        try:
            p._refresh("g", {"turn": 5}, "start of our turn")
        finally:
            claude_cli.run = orig
        self.assertEqual(g["memo"], "good old plan")
        self.assertEqual(p.stats["strategist_errors"], 1)


class PilotAudit(unittest.TestCase):
    def test_blind_audit_maps_verdicts_back_to_pilot_or_forge(self):
        import tempfile
        from edhkit import pilot_audit as A
        self.assertAlmostEqual(A.sign_test(8, 10), 0.109375)
        recs = []
        for i in range(6):
            recs.append({"type": "decision", "game": "g", "turn": i, "phase": "MAIN1", "kind": "action",
                         "state": {"turn": i}, "memo": "m", "context": {},
                         "questions": [{"id": "action", "prompt": "?", "default": "o0",
                                        "options": [{"id": "o0", "text": "forge play"},
                                                    {"id": "o1", "text": "pilot play"}]}],
                         "answers": [{"q": "action", "default": "o0", "choice": "o1"}]})
        recs.append({"type": "decision", "game": "g", "turn": 9, "phase": "MAIN1", "kind": "action",  # agreement
                     "state": {}, "questions": [{"id": "action", "prompt": "?", "options": [{"id": "o0", "text": "x"}]}],
                     "answers": [{"q": "action", "default": "o0", "choice": "o0"}]})
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(json.dumps(r) for r in recs))
        self.assertEqual(len(A.load_overrules(Path(f.name))), 6)

        def judge(prompt, model, effort):  # always prefers the pilot's play, wherever it is shown
            a = prompt.split("\nA: ")[1].split("\n")[0]
            return ("A" if a == "pilot play" else "B") + " — better"
        orig, A._judge = A._judge, judge
        try:
            res = A.audit(Path(f.name), "plan", n=6, workers=2)
        finally:
            A._judge = orig
        self.assertEqual(res["tally"], {"pilot": 6})
        self.assertEqual(res["pilot_share_of_decided"], 1.0)


class PlanMarkers(unittest.TestCase):
    MEMO = ("THIS TURN (10 mana)\n1) Cast Secrets of the Dead ({2}{U}).\n2) Play Polluted Delta from the graveyard.\n"
            "3) Evoke Shriekmaw and kill Herald of War.\n\nTARGET: The Coming of Galactus next turn.\n\n"
            "HOLD: Pernicious Deed until P2 commits more.\nREPLAN IF: a wipe.")

    def test_marks_planned_and_held_cards_only(self):
        from edhkit.pilot import plan_marker
        self.assertIn("step 3", plan_marker(self.MEMO, "cast Shriekmaw (from Graveyard): Evoke {1}{B}"))
        self.assertIn("HOLD", plan_marker(self.MEMO, "activate Pernicious Deed (from Battlefield): {X}, Sacrifice"))
        self.assertEqual(plan_marker(self.MEMO, "cast The Coming of Galactus (from Graveyard): x"), "")  # TARGET only
        self.assertEqual(plan_marker(self.MEMO, "Take no further action this phase"), "")
        self.assertEqual(plan_marker("", "cast Shriekmaw (from Hand): x"), "")

    def test_marker_reaches_jev_and_the_log(self):
        import threading
        from collections import defaultdict
        from edhkit import pilot as P
        seen = {}

        class Capture:
            def evaluate(self, state, questions):
                seen.update(questions)
                return {"action": {"choice": "o1", "probabilities": {"o1": 0.9, "pass": 0.1}}}

        p = P.Pilot.__new__(P.Pilot)
        p.plan, p.strategist, p.model, p.gate, p.pass_gate, p.sync, p.escalate = "plan", "static", "m", 0.1, 0.35, True, False
        p.provider, p.log_dir = Capture(), None
        p._log_lock, p._glock, p._games, p._server = threading.Lock(), threading.Lock(), {}, None
        p.stats = {"errors": 0, "latency_ms": [], "escalations": 0, "escalation_checks": 0,
                   "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}
        logged = []
        p._log = logged.append
        p._maybe_turn_refresh = lambda game, state: None
        p._game("g")["memo"] = self.MEMO
        req = {"game": "g", "kind": "action", "state": {"turn": 3},
               "questions": [{"id": "action", "prompt": "?", "default": "pass",
                              "options": [{"id": "o1", "text": "cast Shriekmaw (from Graveyard): Evoke"},
                                          {"id": "pass", "text": "Take no further action this phase"}]}]}
        self.assertEqual(p.ask(req)["answers"]["action"], "o1")
        self.assertIn("THIS TURN plan, step 3", seen["action"]["criteria"]["o1"])
        self.assertNotIn("memo", seen["action"]["criteria"]["pass"])
        self.assertEqual(logged[-1]["answers"][0]["plan_marked"], ["o1"])


class BigGates(unittest.TestCase):
    """Overrules in decision kinds where Jev's overrules were reliably wrong need the big margin."""

    def _pilot(self, probs):
        import threading
        from collections import defaultdict
        from edhkit import pilot as P

        class Fixed:
            def evaluate(self, state, questions):
                return {qid: {"choice": max(probs, key=probs.get), "probabilities": probs} for qid in questions}

        p = P.Pilot.__new__(P.Pilot)
        p.plan, p.strategist, p.model, p.gate, p.pass_gate, p.sync, p.escalate = "plan", "static", "m", 0.1, 0.35, True, False
        p.provider, p.log_dir = Fixed(), None
        p._log_lock, p._glock, p._games, p._server = threading.Lock(), threading.Lock(), {}, None
        p.stats = {"errors": 0, "latency_ms": [], "escalations": 0, "escalation_checks": 0,
                   "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}
        p._log = lambda rec: None
        p._maybe_turn_refresh = lambda game, state: None
        return p

    def _ask(self, probs, kind, options, default="t0", qid="tgt"):
        req = {"game": "g", "kind": kind, "state": {"turn": 3},
               "questions": [{"id": qid, "prompt": "?", "default": default,
                              "options": [{"id": k, "text": v} for k, v in options.items()]}]}
        return self._pilot(probs).ask(req)["answers"][qid]

    def test_aiming_at_our_own_card_needs_the_big_margin(self):
        opts = {"t0": "The Mouth of Sauron [P1, 3/4, in graveyard]", "t1": "The One Ring [ours, in graveyard]"}
        self.assertEqual(self._ask({"t0": 0.4, "t1": 0.6}, "trigger-target", opts), "t0")
        self.assertEqual(self._ask({"t0": 0.05, "t1": 0.95}, "trigger-target", opts), "t1")
        opts2 = {"t0": "Sauron [P1, 7/6]", "t1": "Zodiark [P2, 8/8]"}  # opponent to opponent: normal margin
        self.assertEqual(self._ask({"t0": 0.4, "t1": 0.6}, "trigger-target", opts2), "t1")

    def test_attacking_where_forge_holds_needs_the_big_margin(self):
        opts = {"hold": "don't attack with it", "d0": "attack P1 (6 life)"}
        self.assertEqual(self._ask({"hold": 0.4, "d0": 0.6}, "attack", opts, default="hold", qid="a0"), "hold")
        opts2 = {"hold": "don't attack with it", "d0": "attack P1 (6 life)"}
        self.assertEqual(self._ask({"hold": 0.6, "d0": 0.4}, "attack", opts2, default="d0", qid="a0"), "hold")


class StrategistCadence(unittest.TestCase):
    def test_plans_every_kth_turn_and_escalation_resets_the_clock(self):
        import threading
        from edhkit import pilot as P
        p = P.Pilot.__new__(P.Pilot)
        p.strategist, p.sync, p.every = "claude-cli", True, 3
        p._glock, p._games = threading.Lock(), {}
        planned = []

        def refresh(game, state, reason):
            g = p._game(game)
            g.update(memo=f"memo@{state['turn']}", pending=False, memo_our_turn=g["our_turns"])
            planned.append((state["turn"], reason))
        p._refresh = refresh
        ages = {}
        for turn in range(1, 41):  # four players; we are active on turns 1, 5, 9, ...
            active = "P1" if turn % 4 == 1 else "P2"
            p._maybe_turn_refresh("g", {"turn": turn, "active": active, "me": "P1"})
            p._maybe_turn_refresh("g", {"turn": turn, "active": active, "me": "P1"})  # later decisions, same turn
            if turn == 21:  # an escalation re-plans mid-turn on our 6th turn
                refresh("g", {"turn": 21}, "executor escalation")
            ages[turn] = p.memo_age(p._game("g"))
        self.assertEqual([t for t, r in planned if r.startswith("start")], [1, 13, 33])
        self.assertIn("next 3 turns", planned[0][1])
        self.assertEqual((ages[1], ages[5], ages[9], ages[13], ages[17]), (0, 1, 2, 0, 1))
        self.assertEqual((ages[21], ages[25], ages[29], ages[33]), (0, 1, 2, 0))


class Replay(unittest.TestCase):
    def test_replay_reports_changed_answers_by_kind(self):
        import tempfile
        from edhkit import pilot as P, replay

        class Fake(P.Pilot):
            def __init__(self, plan, **kw):
                import threading
                from collections import defaultdict
                self.plan, self.strategist, self.escalate, self.gate, self.pass_gate = plan, "static", False, 0.1, 0.35
                self.every, self.log_dir, self.log_state = 1, None, False
                self._games, self._glock, self._log_lock = {}, threading.Lock(), threading.Lock()
                self.stats = {"errors": 0, "latency_ms": [], "escalations": 0, "escalation_checks": 0,
                              "by_kind": defaultdict(lambda: {"requests": 0, "questions": 0, "overrules": 0, "gated": 0})}

                class Prov:
                    def evaluate(self, state, questions):
                        return {q: {"choice": "b", "probabilities": {"a": 0.1, "b": 0.9}} for q in questions}
                self.provider = Prov()

        rec = {"type": "decision", "game": "pod01-g1", "turn": 5, "phase": "MAIN1", "kind": "attack",
               "state": {"turn": 5}, "memo": "", "memo_age": 0, "context": {},
               "questions": [{"id": "a0", "prompt": "Attack with X?", "default": "a",
                              "options": [{"id": "a", "text": "attack P2"}, {"id": "b", "text": "attack P3"}]}],
               "answers": [{"q": "a0", "default": "a", "choice": "a"}]}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pilot_decisions.jsonl").write_text(json.dumps(rec) + "\n")
            orig = replay.P.Pilot
            replay.P.Pilot = Fake
            try:
                res = replay.replay(Path(d), "plan")
            finally:
                replay.P.Pilot = orig
        self.assertEqual(res["by_kind"]["attack"]["changed"], 1)
        self.assertEqual(res["changed"][0]["new"], "attack P3")


class FeedHazards(unittest.TestCase):
    def test_classifies_what_our_plays_feed(self):
        from edhkit.pilot import feed_hazards
        texts = {"Blood Artist": "Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.",
                 "Grave Pact": "Whenever a creature you control dies, each other player sacrifices a creature.",
                 "Patron of the Vein": "Whenever a creature an opponent controls dies, exile it.",
                 "Sauron, the Dark Lord": "Whenever an opponent casts a spell, amass Orcs 1.",
                 "Emblem - Sephiroth": "Whenever a creature dies, target opponent loses 1 life and you gain 1 life.",
                 "Sol Ring": "{T}: Add {C}{C}."}
        state = {"card_text": texts, "players": [
            {"name": "P1", "is_me": True, "battlefield": ["Blood Artist 0/1"]},
            {"name": "P2", "is_me": False, "battlefield": ["Blood Artist 0/1", "Grave Pact", "Patron of the Vein 4/4",
                                                          "Sol Ring", "Sauron, the Dark Lord 7/6"],
             "command_zone_effects": ["Emblem - Sephiroth"]},
            {"name": "P3", "is_me": False, "lost": True, "battlefield": ["Grave Pact"]}]}
        got = feed_hazards(state)
        self.assertEqual(len(got), 5)  # not ours, not Sol Ring, not a player who has lost
        self.assertIn("P2 Grave Pact: triggers on their creatures dying (our removal feeds it)", got)
        self.assertIn("P2 Patron of the Vein: triggers on our creatures dying", got)
        self.assertTrue(any(h.startswith("P2 Emblem") and "any creature dying" in h for h in got))
        self.assertTrue(any(h.startswith("P2 Sauron") and "our spells" in h for h in got))


if __name__ == "__main__":
    unittest.main()
