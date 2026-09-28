"""Regression tests that play a real Forge board for a turn (edhkit/scenario.py). Each one is a bug first found in
a simulated game. They need the Forge build (`./edh forge setup`) and take several seconds each; they are skipped
without it.

    python3 -m unittest tests.test_scenarios
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edhkit import forge  # noqa: E402

HERE = ROOT / "tests" / "scenarios"
DECK = ROOT / "decks" / "vivi-ornitier" / "edhrec-b3" / "deck.txt"


@unittest.skipUnless(forge.find_jar(), "Forge isn't built")
class PilotScenarios(unittest.TestCase):
    def _run(self, name, rules):
        from edhkit import scenario
        sc = scenario.ScriptedSidecar(rules)
        try:
            return scenario.run((HERE / name).read_text(), DECK, players=2, turns=1, pilot_seat=1, sidecar=sc.url)
        finally:
            sc.close()

    def test_aura_on_zero_power_creature_resolves(self):
        """Forge's AI rated Vivi (0/3 base) at -100 for Ophidian Eye and chose nothing at resolution, so the Aura
        stayed stranded in the stack zone and never drew a card (0 triggers in 24 attachments across our runs)."""
        from edhkit.scenario import pick

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if not q:
                return {}
            o = pick(q, "cast Ophidian Eye") or pick(q, "cast Opt")
            return {"action": o or ("pass" if any(x["id"] == "pass" for x in q["options"]) else q["default"])}

        lines = self._run("aura_on_zero_power.txt", rules)
        self.assertTrue(any("Attach to Vivi Ornitier" in ln for ln in lines))
        self.assertTrue(any("triggered Ophidian Eye" in ln for ln in lines), "the Eye on Vivi never triggered")

    def test_counterspell_counters_the_spell(self):
        """With two spells on the stack the pilot asked which to counter and set the Swords *card* as the target;
        Forge's counter effect only acts on spells, so the counter did nothing and Vivi was exiled."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q and not asked and (o := pick(q, "cast Arcane Denial")):
                out["action"] = o
                t = next((x for x in req["questions"] if x["id"] == f"tgt_{o}"), None)
                if t and (tt := pick(t, "Swords")):
                    out[t["id"]] = tt
                    asked.append(1)
            return out

        lines = self._run("counter_two_spells.txt", rules)
        self.assertTrue(asked, "the pilot was never asked which spell to counter")
        self.assertTrue(any("Counter Swords to Plowshares" in ln for ln in lines))
        self.assertFalse(any(ln.startswith("Resolve Stack: Swords to Plowshares") for ln in lines), "Swords resolved")

    def test_modal_trigger_target_is_asked(self):
        """Hullbreaker Horror's trigger is modal; its target sits on the chosen mode, so the pilot was never asked and
        Forge bounced an opponent's creature when the memo's loop needed our own Thought Vessel back."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Opt")):
                    out["action"] = o
                if req["kind"] == "trigger-target" and (o := pick(q, "Thought Vessel")):
                    out[q["id"]] = o
                    asked.append(1)
            return out

        lines = self._run("hullbreaker_own_bounce.txt", rules)
        self.assertTrue(asked, "Hullbreaker's target was never asked")
        self.assertTrue(any("return target nonland permanent" in ln and "(Targeting: Thought Vessel" in ln
                            for ln in lines))


if __name__ == "__main__":
    unittest.main()
