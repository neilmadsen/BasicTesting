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

    def test_multi_card_discard_is_asked(self):
        """Only one-card discards reached the pilot; Frantic Search and Faithless Looting discard two, so Forge's AI
        chose what we threw away."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Frantic Search")):
                    out["action"] = o
                if req["kind"] == "discard":
                    asked.append((q["prompt"], len(q["options"])))
            return out

        lines = self._run("frantic_search_discard.txt", rules)
        self.assertEqual(len(asked), 2, asked)
        self.assertEqual(sum(ln.startswith("Discard:") for ln in lines), 2)
        # the whole hand is on offer: Forge's AI removed its own picks from the list the options were built from
        self.assertEqual([n for _, n in asked], [6, 5], asked)

    def test_storm_copies_are_asked_and_spread(self):
        """Forge's AI aimed every Grapeshot copy at the same 1/1 token (four of five fizzled): each copy is now asked,
        and told what the original and earlier copies already target."""
        from edhkit.scenario import pick
        prompts, taken = [], set()

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action":
                    o = pick(q, "cast Opt") or pick(q, "cast Consider") or pick(q, "cast Grapeshot")
                    if o:
                        out["action"] = o
                if req["kind"] == "trigger-target" and "copy of our Grapeshot" in q["prompt"]:
                    prompts.append(q["prompt"])
                    for o in q["options"]:  # the first P2 creature nobody targets yet
                        name = o["text"].split(" [")[0]
                        if "[P2" in o["text"] and name not in q["prompt"] and name not in taken:
                            taken.add(name)
                            out[q["id"]] = o["id"]
                            break
            return out

        lines = self._run("storm_copies_spread.txt", rules)
        self.assertEqual(len(prompts), 2, prompts)
        self.assertIn("already target", prompts[0])  # the original's target is listed from the first copy on
        self.assertEqual(sum("was put into Graveyard from Battlefield" in ln for ln in lines), 3)

    def test_up_to_x_targets_are_asked(self):
        """Forge's AI aimed an X=2 Crackle with Power at one opponent when the second target would also have died."""
        from edhkit.scenario import pick

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Crackle")):
                    out["action"] = o
                    x = next((qq for qq in req["questions"] if qq["id"] == f"x_{o}"), None)
                    if x:
                        out[x["id"]] = pick(x, "X = 2") or x["default"]
                if q["id"].startswith("tgt_m"):
                    o = pick(q, "P2 (") if q["id"] == "tgt_m0" else pick(q, "P3 (")
                    if o:
                        out[q["id"]] = o
            return out

        from edhkit import scenario
        sc = scenario.ScriptedSidecar(rules)
        try:
            lines = scenario.run((HERE / "crackle_two_targets.txt").read_text(), DECK, players=3, turns=1,
                                 pilot_seat=1, sidecar=sc.url)
        finally:
            sc.close()
        self.assertTrue(any("cast Crackle with Power targeting [Ai(2)-P2, Ai(3)-P3]" in ln for ln in lines))

    def test_priority_with_our_own_spell_on_the_stack(self):
        """The memo planned a response to our own spell (An Offer You Can't Refuse on our own Swiftfoot Boots) and the
        pilot never had priority with it on the stack."""
        from edhkit.scenario import pick
        windows = []

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q and "our own spell is on the stack" in str(req.get("window", "")):
                windows.append(req["window"])
                if (o := pick(q, "cast Consider")):
                    return {"action": o}
            return {}

        lines = self._run("respond_to_own_spell.txt", rules)
        self.assertTrue(windows, "never asked with our own spell on the stack")
        order = [ln for ln in lines if ln.startswith(("Add To Stack: Ai(1)-P1 cast Consider", "Resolve Stack: Opt ("))]
        self.assertTrue(order and order[0].startswith("Add To Stack: Ai(1)-P1 cast Consider"), order)

    def test_modal_spell_mode_is_asked(self):
        """Forge's AI answered nothing for Fire Magic's tiers; 3 of 4 Fire Magics resolved with no effect."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Fire Magic")):
                    out["action"] = o
                if q["id"] == "mode":
                    asked.append([o["text"] for o in q["options"]])
                    if (o := pick(q, "Fira:")):
                        out["mode"] = o
            return out

        lines = self._run("fire_magic_tier.txt", rules)
        self.assertTrue(asked and any("additional cost {2}" in t for t in asked[0]), asked)
        self.assertTrue(any("deals 2 damage to each creature" in ln for ln in lines))

    def test_hold_survives_a_play_vivi_can_pay(self):
        """A hold for a counterspell was dropped for a play Vivi's {0} mana could pay, and the lands paid instead
        (no counter mana for three opposing turns). With UU held for Counterspell, Opt is paid by Vivi."""
        from edhkit.scenario import pick
        later = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action":
                    if (o := pick(q, "cast Opt")):
                        out["action"] = o
                    elif pick(q, "cast Counterspell"):
                        later.append(1)
                if q["id"] == "hold" and (h := pick(q, "for Counterspell")):
                    out["hold"] = h
            return out

        lines = self._run("hold_with_vivi_mana.txt", rules)
        self.assertTrue(any("made Vivi Ornitier's mana to pay for Opt" in ln for ln in lines))
        self.assertTrue(later, "Counterspell was never castable after Opt: the held Islands were spent")

    def test_chosen_mode_is_aimed(self):
        """Forge's AI aims only the mode it would pick: Abrade cast in its other mode had no target and never reached
        the stack ("Couldn't add to stack, failed to target"), three times in round 6."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Abrade")):
                    out["action"] = o
                if q["id"] == "mode":
                    # whichever mode Forge's AI picks, answer the other one
                    other = next(o["id"] for o in q["options"] if o["id"] != q["default"])
                    out["mode"] = other
                    asked.append(next(o["text"] for o in q["options"] if o["id"] == other))
                if req["kind"] == "trigger-target" and "Abrade" in q["prompt"]:
                    t = pick(q, "Horned Turtle") or pick(q, "Sol Ring")
                    if t:
                        out[q["id"]] = t
            return out

        # Forge's AI won't aim 3 damage at a 1/4 it can't kill (nor at our own Bears), so it aims only the artifact mode
        lines = self._run("abrade_creature_mode.txt", rules)
        self.assertTrue(asked)
        self.assertFalse(any("failed to target" in ln for ln in lines), [ln for ln in lines if "Abrade" in ln])
        if "damage" in asked[0]:
            self.assertTrue(any("deals 3 damage to Horned Turtle" in ln for ln in lines), [ln for ln in lines if "Abrade" in ln])

    def test_held_mana_is_not_spent_by_forge(self):
        """With lands held for Arcane Denial, Gitaxian Probe is paid with Vivi's mana (it failed at payment in round 6).
        Forge's own Opt later can still fail at payment when only off-colour floating mana is left (ledger Q): the
        card must then come back to hand, never stay stranded."""
        from edhkit.scenario import pick

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "hold" and (h := pick(q, "for Arcane Denial")):
                    out["hold"] = h
                if q["id"] == "action" and (o := pick(q, "cast Gitaxian Probe")):
                    out["action"] = o
            return out

        lines = self._run("hold_then_forge_pick.txt", rules)
        self.assertTrue(any("made Vivi Ornitier's mana to pay for Gitaxian Probe" in ln for ln in lines))
        self.assertFalse([ln for ln in lines if "Gitaxian Probe" in ln and ("AI failed" in ln or "payment failed" in ln)])
        failed = sum("AI failed to play" in ln for ln in lines)
        self.assertEqual(failed, sum(ln.startswith("[pilot] cast failed at payment") for ln in lines))

    def test_no_vivi_mana_under_linvala(self):
        """Linvala, Keeper of Silence stops our creatures' activated abilities; the pilot offered Vivi's mana 9 times
        under her and made it twice (Forge's canPlay() doesn't check static bans)."""
        from edhkit.scenario import pick
        offered = []

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q and (o := pick(q, "activate Vivi Ornitier")):
                offered.append(o)
                return {"action": o}
            return {}

        lines = self._run("vivi_under_linvala.txt", rules)
        self.assertFalse(offered, "Vivi's mana was offered under Linvala")
        self.assertFalse(any("cast Opt" in ln for ln in lines))

    def test_back_face_is_named_as_itself(self):
        """Birgi, God of Storytelling's back face was offered as "cast Birgi, God of Storytelling (from Hand): Harnfel,
        Horn of Bounty", took the memo's "Cast Birgi" tag, and the artifact was cast instead of the creature."""
        seen = []

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q:
                seen.extend(o["text"] for o in q["options"])
            return {}

        self._run("mdfc_back_face.txt", rules)
        self.assertTrue(any(t.startswith("cast Harnfel, Horn of Bounty (from Hand): [the other face of Birgi") for t in seen), seen)
        self.assertTrue(any(t.startswith("cast Birgi, God of Storytelling (from Hand): Birgi") for t in seen), seen)

    def test_mode_target_is_asked_in_forges_mode_too(self):
        """Forge's own mode was cast at Forge's own target: all 3 Abrades of round 7 hit something the memo didn't name.
        With no artifact on the board there is one legal mode and no mode question; the target is still asked."""
        from edhkit.scenario import pick
        asked = []

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Abrade")):
                    out["action"] = o
                if req["kind"] == "trigger-target" and "Abrade" in q["prompt"]:
                    asked.append([o["text"] for o in q["options"]])
                    # the one Forge didn't pick
                    out[q["id"]] = next(o["id"] for o in q["options"] if o["id"] != q["default"])
            return out

        lines = self._run("abrade_same_mode.txt", rules)
        self.assertTrue(asked, "the target of Abrade's only legal mode was never asked")
        self.assertTrue(any("deals 3 damage to" in ln for ln in lines), [ln for ln in lines if "Abrade" in ln])

    def test_untap_effects_untap_our_lands(self):
        """"Untap up to two lands" was asked blind over every tapped land on the table: 3 of 6 untaps untapped nothing
        and one untapped an opponent's land. Snap paid with both Islands must give both back for two Opts."""
        from edhkit.scenario import pick

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q and (o := pick(q, "cast Snap") or pick(q, "cast Opt")):
                return {"action": o}
            # a blind "choose one" answered as Jev did in round 8
            p = next((q for q in req["questions"] if q["id"] == "pick" and "Snap" in q["prompt"]), None)
            if p and any(o["id"] == "none" for o in p["options"]):
                return {"pick": "none"}
            return {}

        lines = self._run("snap_untaps_ours.txt", rules)
        self.assertTrue(any("cast Snap" in ln for ln in lines))
        self.assertEqual(sum("cast Opt" in ln for ln in lines if ln.startswith("Add To Stack")), 2, [ln for ln in lines if "Opt" in ln or "Snap" in ln])

    def test_vivi_mana_covers_the_colour_lands_lack(self):
        """Vivi's mana was split by the pips in hand: 1 mana came out red beside an untapped Mountain, and the planned
        Sigil of Sleep ({U}) couldn't be cast. The colour no untapped land makes comes first."""
        from edhkit.scenario import pick

        def rules(req):
            q = next((q for q in req["questions"] if q["id"] == "action"), None)
            if q and (o := pick(q, "activate Vivi Ornitier") or pick(q, "cast Sigil of Sleep")):
                return {"action": o}
            return {}

        lines = self._run("vivi_colour_split.txt", rules)
        self.assertTrue(any("cast Sigil of Sleep" in ln for ln in lines), [ln for ln in lines if "pilot" in ln or "Sigil" in ln])

    def test_filter_mana_from_the_pool(self):
        """Forge's payment can't pay Izzet Signet's {1} from floating mana and then spend its {U}{R}: Jeska's Will,
        Chaos Warp and Fire Magic failed at payment with 2 floating and an untapped Signet (ledger J)."""
        from edhkit.scenario import pick

        def rules(req):
            out = {}
            for q in req["questions"]:
                if q["id"] == "action" and (o := pick(q, "cast Chaos Warp")):
                    out["action"] = o
                if q["id"].startswith("tgt_") and (t := pick(q, "Grizzly Bears")):
                    out[q["id"]] = t
            return out

        lines = self._run("signet_filter_from_pool.txt", rules)
        self.assertFalse([ln for ln in lines if "AI failed to play" in ln])
        self.assertTrue(any(ln.startswith("Resolve Stack: Chaos Warp") for ln in lines), [ln for ln in lines if "Warp" in ln or "pilot" in ln])


if __name__ == "__main__":
    unittest.main()
