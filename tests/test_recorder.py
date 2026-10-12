"""The human-play recorder (pilot/src/edh/pilot/Recorder.java, edhkit/play.py).

    python3 -m unittest tests.test_recorder

The fast tests check the reader and the verifier on a small hand-written session. The Forge test plays a whole
4-player game with the recorder on an AI seat (its test mode) and checks the recording against Forge's own log of
the game: every cast, activation, land drop, attacker and blocker, in order, each matched to an offered option.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edhkit import forge, play  # noqa: E402

DECK = ROOT / "decks" / "obeka-splitter-of-seconds" / "many-mornings" / "deck.txt"


def _decision(turn, kind, choice, label, options, phase="MAIN1"):
    qid = {"action": "action", "attack": "attackers", "block": "blockers", "mulligan": "keep"}[kind]
    return {"type": "decision", "game": "g1", "by": "human", "turn": turn, "phase": phase, "kind": kind, "ms": 1200,
            "context": {"window": "our main phase 1 (before combat), stack empty"},
            "questions": [{"id": qid, "prompt": "?", "default": "pass",
                           "options": [{"id": i, "text": t} for i, t in options]}],
            "answers": [{"q": qid, "default": "pass", "choice": choice, "label": label}],
            "state": {"turn": turn, "my_hand": ["Island"], "my_mana_available": 3,
                      "players": [{"name": "Neil", "is_me": True, "life": 40, "battlefield": []},
                                  {"name": "P2", "is_me": False, "life": 38, "battlefield": []}]}}


class Reader(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        recs = [
            {"type": "game_start", "game": "g1", "by": "human", "me": "Neil", "me_name": "Neil",
             "players": [{"name": "Neil", "is_me": True, "commanders": ["Obeka, Splitter of Seconds"]},
                         {"name": "P2", "is_me": False, "commanders": ["Edgar Markov"]}]},
            _decision(1, "mulligan", "keep", "keep the hand", [("keep", "keep the hand"), ("mulligan", "mulligan")]),
            _decision(2, "action", "o0", "play land Island", [("o0", "play land Island"), ("pass", "pass")]),
            _decision(2, "action", "o1", "cast Counterspell targeting Edgar Markov",
                      [("o0", "cast Sol Ring: add"), ("o1", "cast Counterspell: counter"), ("pass", "pass")]),
            _decision(4, "attack", "o0", "Obeka, Splitter of Seconds -> P2",
                      [("o0", "Obeka, Splitter of Seconds 2/5"), ("none", "no attack")], "COMBAT_DECLARE_ATTACKERS"),
            {"type": "outcome", "game": "g1", "turn": 9, "winner": "Neil", "we_won": True, "records": 5,
             "recorder_errors": 0},
        ]
        (self.dir / "human_decisions.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        (self.dir / "g1.log").write_text("\n".join([
            "Land: Neil played Island (12)",
            "Add To Stack: Neil cast Counterspell targeting [Edgar Markov (40)]",
            "Combat: Neil assigned Obeka, Splitter of Seconds (3) to attack P2.",
        ]) + "\n")

    def test_verify_matches_the_log(self):
        g = play.verify(self.dir)[0]
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["checks"]["plays: log vs recorded"], (2, 2))
        self.assertEqual(g["checks"]["attackers: log vs recorded"], (1, 1))

    def test_verify_catches_a_missing_play(self):
        log = self.dir / "g1.log"
        log.write_text(log.read_text() + "Add To Stack: Neil cast Swan Song targeting [Damnation (77)]\n")
        self.assertFalse(play.verify(self.dir)[0]["ok"])

    def test_show_lists_decisions_and_options(self):
        text = play.show(self.dir)
        self.assertIn("cast Counterspell targeting Edgar Markov", text)
        self.assertIn("could: cast Sol Ring; cast Counterspell", text)
        self.assertIn("winner Neil (you)", text)


@unittest.skipUnless(forge.find_jar(), "Forge isn't built")
class RecordedGame(unittest.TestCase):
    def test_full_game_recording_matches_forge_log(self):
        out = Path(tempfile.mkdtemp())
        decks = play.write_decks(DECK, 3, out / "decks")
        names = {p.stem: p for p in decks}
        pod = [decks[0], names["Gauntlet B3 - Edgar Markov"], names["Gauntlet B3 - Pantlaza, Sun-Favored"],
               names["Gauntlet B3 - Sauron, the Dark Lord"]]
        cmd = play.java_cmd(["--headless-test", "--out", str(out / "rec"), "--turns", "40", "--seed", "7",
                             *map(str, pod)], headless=True)
        r = subprocess.run(cmd, cwd=forge.res_dir(), capture_output=True, text=True, timeout=1500)
        self.assertIn("[recorder-test]", r.stdout, r.stderr[-2000:])
        games = play.verify(out / "rec")
        self.assertEqual(len(games), 1)
        g = games[0]
        self.assertTrue(g["ok"], g)
        plays = g["checks"]["plays: log vs recorded"]
        self.assertGreater(plays[0], 5)  # a real game, not an empty one


if __name__ == "__main__":
    unittest.main()
