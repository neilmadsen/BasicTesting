"""Bug scan: invariants every simulated game should satisfy, checked against the Forge game log and the pilot
log. No model calls; run it on every sim.

    ./edh bugscan <sim-out> [<sim-out> ...] [--json out.json]

Each check is one class of bug found by hand in a single game, turned into a rule that runs on every game:
- counter-fizzle: our counterspell resolved and its target resolved anyway (a spell targeted as a card);
- damage-trigger-missing: a creature wearing our "whenever enchanted/equipped creature deals damage" Aura or
  Equipment dealt that damage and the trigger never went on the stack;
- once-per-turn: a "once each turn" ability the pilot activated twice in one turn;
- wasted-mana: the pilot made mana (Vivi's {0}) and spent none of it before the phase ended;
- equip-pingpong: one Equipment moved more than twice in a turn;
- forge-trigger-targets: our targeted or modal triggers whose target Forge's AI chose without asking the pilot;
- stranded-aura: our Aura logged as attached but never reached our battlefield;
- decked: we lost by drawing from an empty library;
- hook-errors: pilot hooks that failed and fell back to Forge;
- scan-truncated: the pilot's option scan ran out of time, so some plays were never offered;
- cast-failed: Forge's AI failed to pay for a cast of ours;
- false-rescue: the pilot returned a card to hand after a cast that hadn't failed;
- strategist-failed: strategist calls failed, so the game ran on an old memo (a contaminated game);
- cast-stranded: a failed cast whose card was never returned (it stays in the stack zone);
- stale-freeze: a cast found the stack still frozen by an earlier failed payment;
- chosen-play-not-made: the pilot chose a cast the game never made;
- untagged-plan: an option for a card the fresh memo names as a play carried no plan tag (a tagging miss).

Severity: high = changes games and is certainly wrong; medium = likely wrong, check the evidence; low = a lead
for the turn auditor, often legitimate.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .scorecard import _log, _open, pod_games

_TURN = re.compile(r"^Turn: Turn (\d+) \(Ai\(\d+\)-(P\d+)\)")
_TARGETS = re.compile(r"(.+?) \((\d+)\)(?:, |$)")
_ATTACH = re.compile(r"^Resolve Stack: (.+?) \((\d+)\) -  Attach to (.+?) \((\d+)\)")
_LEAVES = re.compile(r"^Zone Change: (.+?) \((\d+)\) was put into (\w+) from Battlefield")
_DAMAGE = re.compile(r"^Damage: (.+?) \((\d+)\) deals (\d+) (non-combat |combat )?damage to Ai\(\d+\)-(P\d+)")
_ATTACHED_TRIGGER = re.compile(r"whenever (?:enchanted|equipped) creature deals (combat )?damage to "
                               r"(an opponent|a player|one or more players|a player or planeswalker)", re.I)
_MANA_OPTION = re.compile(r"^activate (.+?) \(from Battlefield\): add (\d+) mana .* to our mana pool now")
_ONCE = re.compile(r"only once each turn|activate only once each turn|once each turn", re.I)
_RESOLVE_TARGETED = re.compile(r"^Resolve Stack: ((?:Whenever|When|At) .+?) \(Targeting: (.+?)\) \[Card: .*?Activator: "
                               r"Ai\(\d+\)-(P\d+)")


class _Oracle:
    def __init__(self):
        try:
            from .cards import CardDB
            self.db = CardDB()
        except BaseException:  # no DB: checks that need rules text are skipped
            self.db = None
        self.cache: dict[str, str] = {}

    def text(self, name: str) -> str:
        if name not in self.cache:
            card = self.db.get(name) if self.db else None
            self.cache[name] = (card.text or "") if card else ""
        return self.cache[name]


def _aura_type(oracle: "_Oracle", name: str) -> str:
    card = oracle.db.get(name) if oracle.db else None
    return card.type_line if card else ""


def _finding(check, sev, game, turn, what, evidence=()):
    return {"check": check, "severity": sev, "game": game, "turn": turn, "what": what,
            "evidence": [e[:220] for e in evidence][:6]}


def _turn_index(lines):
    """Line index -> turn number (None before turn 1)."""
    out, turn = [], None
    for line in lines:
        m = _TURN.match(line)
        if m:
            turn = int(m.group(1))
        out.append(turn)
    return out


def scan_game(key: str, us: str, body: str, decisions: list[dict], oracle: _Oracle) -> list[dict]:
    lines = body.splitlines()
    turns = _turn_index(lines)
    found = []
    ours = rf"Ai\(\d+\)-{us}"

    # counter-fizzle
    for i, line in enumerate(lines):
        m = re.match(rf"^Add To Stack: {ours} cast (.+?) targeting \[(.+)\]$", line)
        if not m or "counter target" not in oracle.text(m.group(1)).lower():
            continue
        spell = m.group(1)
        targets = _TARGETS.findall(m.group(2))
        if not targets:  # a spell targeted as a spell prints its text; the resolution names what it countered
            later = lines[i + 1:i + 200]
            res = next((x for x in later if x.startswith(f"Resolve Stack: {spell} (")), None)
            if res and (c := re.search(r" - Counter (.+?) \((\d+)\)", res)):
                targets = [(c.group(1), c.group(2))]
            elif res and " - Counter." in res:
                found.append(_finding("counter-fizzle", "high", key, turns[i],
                                      f"{spell} resolved without countering anything", [line, res]))
        for tname, tid in targets:
            later = lines[i + 1:i + 200]
            mine = next((j for j, x in enumerate(later) if x.startswith(f"Resolve Stack: {spell} (")), None)
            theirs = next((j for j, x in enumerate(later) if x.startswith(f"Resolve Stack: {tname} ({tid})")), None)
            # the card named in between came back some other way (Victimize returned a countered Scarab God, whose
            # own ability then resolved under its name)
            back = mine is not None and theirs is not None and any(f"({tid})" in x for x in later[mine + 1:theirs])
            if mine is not None and theirs is not None and theirs > mine and not back:
                found.append(_finding("counter-fizzle", "high", key, turns[i],
                                      f"{spell} resolved, then its target {tname} resolved anyway",
                                      [line, later[mine], later[theirs]]))

    # damage-trigger-missing
    cast_by_us = {m.group(1) for line in lines
                  if (m := re.match(rf"^Add To Stack: {ours} (?:cast|activated) (.+?)(?: targeting .*)?$", line))}
    attached = {}  # aura/equipment id -> (name, creature id, needs combat, targeted)
    expected, seen, first = Counter(), Counter(), {}
    last_caster = {}  # card name -> who cast it last: an opponent's own Ophidian Eye isn't ours
    for i, line in enumerate(lines):
        if c := re.match(r"^Add To Stack: (Ai\(\d+\)-P\d) cast (.+?)(?: targeting .*)?$", line):
            last_caster[c.group(2)] = c.group(1)
        if m := _ATTACH.match(line):
            name, aid, cid = m.group(1), m.group(2), m.group(4)
            t = _ATTACHED_TRIGGER.search(oracle.text(name))
            ours_now = re.fullmatch(ours, last_caster.get(name, "")) is not None or name not in last_caster
            if name in cast_by_us and t and ours_now:
                rest = oracle.text(name)[t.end():t.end() + 120].lower()
                attached[aid] = (name, cid, bool(t.group(1)), "target" in rest.split(".")[0])
            else:
                attached.pop(aid, None)
        elif m := _LEAVES.match(line):
            gone = m.group(2)
            attached.pop(gone, None)
            for aid in [a for a, v in attached.items() if v[1] == gone]:
                attached.pop(aid)
        elif m := _DAMAGE.match(line):
            src, target = m.group(2), m.group(5)
            if target == us:
                continue
            # damage that ends the game leaves no time for the trigger
            tail = lines[i + 1:i + 14]
            end = next((j for j, x in enumerate(tail) if x.startswith("Game Outcome")), None)
            if end is not None and not any(x.startswith("Add To Stack") for x in tail[:end]):
                continue
            for aid, (name, cid, combat, targeted) in attached.items():
                if cid == src and (not combat or m.group(4) == "combat "):
                    k = (turns[i], name, targeted)
                    expected[k] += 1
                    first.setdefault(k, line)
        elif m := re.match(rf"^Add To Stack: {ours} triggered (.+?)(?: targeting \[.*)?$", line):
            for k in list(expected):
                if k[0] == turns[i] and k[1] == m.group(1).strip():
                    seen[k] += 1
    for k, n in expected.items():
        if seen[k] < n:
            turn, name, targeted = k
            found.append(_finding("damage-trigger-missing", "low" if targeted else "high", key, turn,
                                  f"{name}: {n} qualifying damage events, {seen[k]} triggers",
                                  [first[k]]))

    # stranded-aura: our Aura "attached" but is on our battlefield at none of our later decisions, and no zone
    # change took it away (Forge's AI chose nothing at resolution and left it in the stack zone)
    for i, line in enumerate(lines):
        m = _ATTACH.match(line)
        if not m or m.group(1) not in cast_by_us or "Aura" not in _aura_type(oracle, m.group(1)):
            continue
        name, aid = m.group(1), m.group(2)
        gone = any(x.startswith(f"Zone Change: {name} ({aid})") for x in lines[i + 1:])
        later = [d for d in decisions if (d.get("turn") or 0) > (turns[i] or 0)][:1]
        if not gone and later:
            me = next((p for p in later[0]["state"].get("players", []) if p.get("is_me")), {})
            if not any(e.split(" [")[0].split(" {")[0].strip() == name for e in me.get("battlefield", [])):
                found.append(_finding("stranded-aura", "high", key, turns[i],
                                      f"{name} resolved onto {m.group(3)} but never reached our battlefield", [line]))

    # equip-pingpong
    moves = Counter()
    for i, line in enumerate(lines):
        m = re.match(rf"^Add To Stack: {ours} activated (.+?) targeting", line)
        if m and re.search(r"^Equip\b|\bEquip [{\d]", oracle.text(m.group(1)), re.M):
            moves[(turns[i], m.group(1))] += 1
    for (turn, name), n in moves.items():
        if n > 2:
            found.append(_finding("equip-pingpong", "medium", key, turn, f"{name} moved {n} times"))

    # forge-trigger-targets: our targeted triggers; the pilot asked about only `asked` of them that turn
    asked = Counter(d["turn"] for d in decisions if d.get("kind") == "trigger-target")
    by_turn = defaultdict(list)
    for i, line in enumerate(lines):
        m = _RESOLVE_TARGETED.match(line)
        if m and m.group(3) == us:
            by_turn[turns[i]].append((m.group(1)[:70], m.group(2)))
    for turn, items in by_turn.items():
        unseen = len(items) - asked.get(turn, 0)
        if unseen > 0:
            kinds = Counter(t for t, _ in items)
            found.append(_finding("forge-trigger-targets", "medium", key, turn,
                                  f"{unseen} of {len(items)} targeted triggers of ours had Forge-chosen targets: "
                                  + "; ".join(f"{t}… ×{n}" for t, n in kinds.most_common(3)),
                                  [f"{t} -> {tgt}" for t, tgt in items]))

    # decked
    if re.search(rf"^Game Outcome: {ours} has lost trying to draw cards from empty library", body, re.M):
        ours_t = [int(m.group(1)) for x in lines if (m := _TURN.match(x)) and m.group(2) == us]
        last = ours_t[-1] if ours_t else max((t for t in turns if t is not None), default=None)
        found.append(_finding("decked", "high", key, last, "we lost by drawing from an empty library"))

    found += _scan_decisions(key, decisions, oracle)

    # chosen-play-not-made: the pilot chose to cast a card more often in a turn than the log shows it cast (payment
    # failed, the option was never really castable, or the answer wasn't applied)
    chosen = Counter()
    for d in decisions:
        if d.get("kind") != "action":
            continue
        q = next((q for q in d["questions"] if q["id"] == "action"), None)
        a = next((a for a in d["answers"] if a["q"] == "action"), None)
        if q and a and a["choice"] != "pass":
            m = re.match(r"^cast (.+?) \(from (\w+)\)", _opts(q).get(a["choice"], ""))
            if m:
                chosen[(d["turn"], m.group(1))] += 1
    cast = Counter()
    for i, line in enumerate(lines):
        m = re.match(rf"^Add To Stack: {ours} cast (.+?)(?: targeting .*)?$", line)
        if m:
            cast[(turns[i], m.group(1))] += 1
    for (turn, name), n in chosen.items():
        if cast[(turn, name)] < n:
            found.append(_finding("chosen-play-not-made", "medium", key, turn,
                                  f"the pilot chose to cast {name} {n}x; the log shows {cast[(turn, name)]}"))
    return found


def _opts(q):
    return {o["id"]: o["text"] for o in q["options"]}


def _scan_decisions(key: str, decisions: list[dict], oracle: _Oracle) -> list[dict]:
    """Checks on the pilot's own decisions: once-per-turn activations, mana made and not spent, plan tags."""
    from . import pilot as P
    found = []
    acts = [d for d in decisions if d.get("kind") == "action"]
    once = Counter()
    for n, d in enumerate(acts):
        q = next((q for q in d["questions"] if q["id"] == "action"), None)
        a = next((a for a in d["answers"] if a["q"] == "action"), None)
        if not q or not a:
            continue
        text = _opts(q).get(a["choice"], "")
        m = _MANA_OPTION.match(text)
        if not m:
            continue
        if _ONCE.search(oracle.text(m.group(1))) or "Once per turn" in text:
            once[(d["turn"], m.group(1))] += 1
        spent = False
        for later in acts[n + 1:]:
            if later["turn"] != d["turn"] or later.get("phase") != d.get("phase"):
                break
            lq = next((x for x in later["questions"] if x["id"] == "action"), None)
            la = next((x for x in later["answers"] if x["q"] == "action"), None)
            if lq and la and la["choice"] != "pass" and not _MANA_OPTION.match(_opts(lq).get(la["choice"], "")):
                spent = True
                break
        if not spent:
            hand = d["state"].get("my_hand", [])
            found.append(_finding("wasted-mana", "medium", key, d["turn"],
                                  f"{m.group(1)} made {m.group(2)} mana in {d.get('phase')} and nothing was cast "
                                  f"after it; hand: {', '.join(hand) or 'empty'}"))
    cut = [d for d in acts if (d.get("context") or {}).get("scan_truncated")]
    if cut:
        found.append(_finding("scan-truncated", "high", key, cut[0]["turn"],
                              f"{len(cut)} action decisions listed only part of what we could play: "
                              + cut[0]["context"]["scan_truncated"]))
    for (turn, name), n in once.items():
        if n > 1:
            found.append(_finding("once-per-turn", "high", key, turn, f"{name}'s once-per-turn mana used {n} times"))

    # untagged-plan: a fresh memo names the card as a play, it is on offer, and the tagger gave it nothing
    for d in acts:
        if not d.get("memo") or (d.get("memo_age") or 0) > 0:
            continue
        plan = P.memo_sections(d["memo"]).get("THIS TURN", "")
        q = next((q for q in d["questions"] if q["id"] == "action"), None)
        if not q or not plan:
            continue
        tags = P.option_tags({"kind": "action", "state": d["state"], "questions": d["questions"]}, d["memo"], 0)
        for oid, text in _opts(q).items():
            m = P._OPTION_CARD.match(text)
            if not m or tags.get("action", {}).get(oid, "").strip():
                continue
            name = m.group(1)
            for at in P._card_matches(plan, name):
                start = max(plan.rfind(". ", 0, at), plan.rfind("\n", 0, at), plan.rfind(";", 0, at)) + 1
                prefix = plan[start:at]
                verb = re.search(r"\b(cast|play|activate|equip|recast|flash)\s+(?:\w+\s+){0,1}$", prefix, re.I)
                if verb and not P._HOLD_WORDS.search(prefix):
                    found.append(_finding("untagged-plan", "low", key, d["turn"],
                                          f"{name} is on offer and the memo says \"{prefix.strip()[-40:]} {name}\", "
                                          f"but the option has no plan tag", [text[:120]]))
                    break
    return found


def _dedupe(found):
    seen, out = set(), []
    for f in found:
        k = (f["check"], f["game"], f["turn"], f["what"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def scan(sim: Path) -> list[dict]:
    oracle = _Oracle()
    decisions = defaultdict(list)
    memo_errors = defaultdict(list)
    try:
        for line in _open(_log(sim)):
            r = json.loads(line)
            if r.get("type") == "decision":
                decisions[r["game"]].append(r)
            elif r.get("type") == "memo_error":
                memo_errors[r["game"]].append(r)
    except FileNotFoundError:
        pass
    found = []
    # failed strategist calls: the pilot runs on an old memo, so the game says little about the strategist
    for game, errs in sorted(memo_errors.items()):
        found.append(_finding("strategist-failed", "high", game, errs[0].get("turn"),
                              f"{len(errs)} strategist calls failed from turn {errs[0].get('turn')}: "
                              + str(errs[0].get("error", ""))[:120]))
    for pod, g, us, body in pod_games(sim):
        key = f"{pod}-g{g}"
        found += scan_game(key, us, body, decisions.get(key, []), oracle)
    # casts Forge's AI failed to pay for: the card used to stay in the stack zone for the rest of the game
    for pod in sorted(list(sim.glob("pod*.log")) + list(sim.glob("pod*.log.gz"))):
        text = _open(pod).read()
        head = re.search(r"^# seats: (.*)$", text, re.M)
        us = next((k for k, v in json.loads(head.group(1)).items() if v == "US"), None) if head else None
        if us:
            fails = re.findall(rf"^\[Ai\(\d+\)-{us}\] AI failed to play (.+?) \(\d+\)", text, re.M)
            if fails:
                found.append(_finding("cast-failed", "high", pod.name.split(".")[0], None,
                                      f"{len(fails)} of our casts failed at payment: " + ", ".join(fails[:6])))
            # a rescue with no payment failure behind it moved a card that was really being cast (duplicated it)
            rescued = re.findall(r"^\[pilot\] cast failed at payment[,;] returned (.+?)(?: to \w+| and made .*)$", text, re.M)
            extra = [n for n in rescued if rescued.count(n) > fails.count(n)]
            if extra:
                found.append(_finding("false-rescue", "high", pod.name.split(".")[0], None,
                                      "cards sent back without a failed payment: " + ", ".join(sorted(set(extra)))))
            # a failure with no rescue: the card stayed in the stack zone (Vivi, for a whole game)
            stuck = [n for n in set(fails) if fails.count(n) > rescued.count(n)]
            if stuck:
                why = re.findall(r"^\[pilot\] payment failed for (.+)$", text, re.M)
                found.append(_finding("cast-stranded", "high", pod.name.split(".")[0], None,
                                      "failed casts never returned: " + ", ".join(sorted(stuck))
                                      + (f"; {why[0][:200]}" if why else "")))
            stale = re.findall(r"^\[pilot\] stale stack freeze cleared before casting (.+)$", text, re.M)
            if stale:
                found.append(_finding("stale-freeze", "medium", pod.name.split(".")[0], None,
                                      f"{len(stale)} casts found the stack frozen by an earlier failure: "
                                      + ", ".join(stale[:6])))
    run = sim / "run.txt"
    if run.exists():
        m = re.search(r"HOOK ERRORS \(fell back to Forge\): (.+)", run.read_text())
        if m:
            found.append(_finding("hook-errors", "medium", sim.name, None, m.group(1).strip()))
    return _dedupe(found)


_ORDER = {"high": 0, "medium": 1, "low": 2}


def report(results: dict[str, list[dict]], show: int = 4) -> str:
    out = []
    for name, found in results.items():
        by = defaultdict(list)
        for f in found:
            by[(f["severity"], f["check"])].append(f)
        out.append(f"== {name}: " + (", ".join(f"{c} {s} ×{len(v)}" for (s, c), v in
                                             sorted(by.items(), key=lambda kv: _ORDER[kv[0][0]])) or "clean"))
        for (sev, check), items in sorted(by.items(), key=lambda kv: _ORDER[kv[0][0]]):
            for f in items[:show]:
                out.append(f"  [{sev}] {check} {f['game']} t{f['turn']}: {f['what']}")
                for e in f["evidence"][:2]:
                    out.append(f"      {e}")
            if len(items) > show:
                out.append(f"  ... {len(items) - show} more {check}")
    return "\n".join(out)


def main(paths: list[str], json_out: str | None = None, show: int = 4) -> None:
    results = {Path(p).name: scan(Path(p)) for p in paths}
    print(report(results, show))
    if json_out:
        Path(json_out).write_text(json.dumps(results, indent=1))
