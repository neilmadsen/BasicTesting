# Plan adherence: of the deck cards a start-of-turn memo says to play this turn, how many we played.
# Usage: python3 research/plan_adherence.py <sim-out-dir> [...]  (needs a --log-state pilot log)
MANA = {'Island', 'Talisman of Dominance', 'Mind Stone', 'Zagoth Triome', 'Darkslick Shores', 'Takenuma, Abandoned Mire', 'Bayou', 'Wooded Foothills', 'Breeding Pool', 'Command Tower', 'Forest', 'Arcane Signet', 'Verdant Catacombs', 'Woodland Cemetery', 'Tropical Island', 'Otawara, Soaring City', 'Bloodstained Mire', 'Bojuka Bog', 'Watery Grave', 'Polluted Delta', 'Waterlogged Grove', 'Cabal Pit', 'Overgrown Tomb', 'Scalding Tarn', 'Marsh Flats', 'Hinterland Harbor', 'Swamp', 'Boseiju, Who Endures', 'Nurturing Peatland', 'Underground Sea', 'Misty Rainforest', 'Drowned Catacomb', 'Sol Ring'}
"""Plan adherence: of the deck cards a start-of-turn memo tells us to play this turn, how many did we play?"""
import json, re, sys, collections
sys.path.insert(0, "/home/user/BasicTesting")
from edhkit.deck import Deck
deck = Deck.load("decks/muldrotha-the-gravetide/undertaker/deck.txt")
names = sorted({e.name.split(" // ")[0] for e in deck.commanders + deck.main}, key=len, reverse=True)
names = [n for n in names if n not in MANA]
def mentioned(text):
    out, t = [], text
    for n in names:
        short = n.split(",")[0]
        if n in t or (len(short) > 5 and re.search(r"\b" + re.escape(short) + r"\b", t)):
            out.append(n); t = t.replace(n, " ")
    return out
def plan_line(memo):
    m = re.search(r"(THIS TURN|PRIORITIES):(.*?)(\n[A-Z &]+:|\Z)", memo, re.S)
    return m.group(2) if m else ""
for arm in sys.argv[1:]:
    recs = [json.loads(l) for l in open(arm + "/pilot_decisions.jsonl")]
    played = collections.defaultdict(set)   # (game, turn) -> card names we chose to play
    offered = collections.defaultdict(set)  # cards offered to the executor that turn
    for r in recs:
        if r["type"] == "decision" and r["kind"] == "action":
            for a in r["answers"]:
                if a["q"] != "action": continue
                m = re.match(r"(?:cast|activate|play land) (.+?) \(from", a["label"])
                if m: played[(r["game"], r["turn"])].add(m.group(1))
                for q in r.get("questions", []):
                    if q["id"] == "action":
                        for o in q["options"]:
                            mo = re.match(r"(?:cast|activate|play land) (.+?) \(from", o["text"])
                            if mo: offered[(r["game"], r["turn"])].add(mo.group(1))
    planned = done = offered_n = 0; misses = collections.Counter()
    for r in recs:
        if r["type"] != "memo" or r["reason"] != "start of our turn": continue
        cards = mentioned(plan_line(r["memo"]))
        key = (r["game"], r["turn"])
        for c in cards:
            planned += 1
            short = c.split(",")[0]
            hit = any(p.startswith(short) or short in p for p in played[key])
            done += hit
            if offered.get(key) is not None:
                off = any(p.startswith(short) or short in p for p in offered[key])
                offered_n += off
                if not hit: misses["offered but not chosen" if off else "never offered to the executor"] += 1
            elif not hit:
                misses["not hit (no option log)"] += 1
    print(f"{arm.split('/')[-1]}: planned {planned} card plays; carried out {done} ({done/max(1,planned):.0%}); misses: {dict(misses)}")

print("\n--- refined: only planned cards that were in hand / graveyard / on our battlefield at memo time ---")
sys.path.insert(0, "/home/user/BasicTesting")
from edhkit.pilot import parse_entry
for arm in sys.argv[1:]:
    recs = [json.loads(l) for l in open(arm + "/pilot_decisions.jsonl")]
    played = collections.defaultdict(set); offered = collections.defaultdict(set); first_state = {}
    for r in recs:
        if r["type"] == "decision":
            key = (r["game"], r["turn"])
            if "state" in r and key not in first_state: first_state[key] = r["state"]
            if r["kind"] == "action":
                for a in r["answers"]:
                    if a["q"] != "action": continue
                    m = re.match(r"(?:cast|activate|play land) (.+?) \(from", a["label"])
                    if m: played[key].add(m.group(1))
                for q in r.get("questions", []):
                    if q["id"] == "action":
                        for o in q["options"]:
                            mo = re.match(r"(?:cast|activate|play land) (.+?) \(from (\w+)", o["text"])
                            if mo: offered[key].add(mo.group(1))
    cats = collections.Counter(); examples = collections.defaultdict(list)
    for r in recs:
        if r["type"] != "memo" or r["reason"] != "start of our turn": continue
        key = (r["game"], r["turn"]); st = first_state.get(key)
        if not st: continue
        me = next(p for p in st["players"] if p["is_me"])
        zones = {"hand": st["my_hand"], "graveyard": st["my_graveyard"],
                 "battlefield": [parse_entry(e)["name"] for e in me["battlefield"]], "command": st["my_command_zone"]}
        for c in mentioned(plan_line(r["memo"])):
            short = c.split(",")[0]
            zone = next((z for z, cards in zones.items() if any(short in x for x in cards)), None)
            if not zone: cats["planned card not in hand/graveyard/battlefield/command (tutor or draw target)"] += 1; continue
            hit = any(short in p for p in played[key]); off = any(short in p for p in offered[key])
            gy_muld = zone == "graveyard" and not any("Muldrotha" in x for x in zones["battlefield"])
            tag = ("done" if hit else "offered, not chosen" if off else
                   "not offered: in graveyard while Muldrotha not on battlefield" if gy_muld else f"not offered: in {zone}")
            cats[tag] += 1
            if tag.startswith("not offered: in") and len(examples[tag]) < 4:
                examples[tag].append((r["game"], r["turn"], c, me and st.get("my_mana_available")))
    tot = sum(v for k, v in cats.items() if not k.startswith("planned card not"))
    print(f"\n{arm.split('/')[-1]}: of {tot} planned plays of cards we had access to:")
    for k, v in cats.most_common():
        print(f"   {v:4d}  {k}" + (f"  ({v/tot:.0%})" if not k.startswith("planned card not") else ""))
    for k, ex in examples.items():
        print(f"   e.g. {k}: {ex}")
