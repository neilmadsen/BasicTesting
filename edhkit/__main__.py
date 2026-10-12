"""`./edh` command line. Run `./edh -h` or `./edh <command> -h`."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from .paths import CARDS_DB, GAUNTLET, ensure_dirs


# --------------------------------------------------------------------------- shared args

def add_pool_args(p: argparse.ArgumentParser, default_limit: int | None = 50, default_lands: str = "any") -> None:
    g = p.add_argument_group("card pool filters")
    g.add_argument("--ci", help="color identity: WUBRG letters, 'C', or commander name(s) joined with ' + '")
    g.add_argument("--type", action="append", default=[], help="type line must contain (repeatable, AND)")
    g.add_argument("--not-type", action="append", default=[], help="type line must not contain")
    g.add_argument("--text", help="FTS5 query over name/type/text, e.g. 'proliferate OR \"+1/+1 counter\"'")
    g.add_argument("--regex", help="Python regex over rules text (case-insensitive)")
    g.add_argument("--tag", action="append", default=[], help="Scryfall tagger role tag (AND); see `edh tags list`")
    g.add_argument("--any-tag", action="append", default=[], help="role tag (OR)")
    g.add_argument("--mv", help="mana value: '3', '<=3', '2-4', '>=6'")
    g.add_argument("--gc", choices=["any", "exclude", "only"], default="any", help="Game Changers")
    g.add_argument("--lands", choices=["any", "exclude", "only"], default=default_lands)
    g.add_argument("--commanders-only", action="store_true", help="only cards that can be commanders")
    g.add_argument("--min-rank", type=int, help="EDHREC rank ≥ N (bigger = less played; hunts obscure cards)")
    g.add_argument("--max-rank", type=int, help="EDHREC rank ≤ N (popular cards only)")
    g.add_argument("--after", help="released on/after YYYY-MM-DD")
    g.add_argument("--no-commons", action="store_true",
                   help="skip cards whose canonical printing is common (jev: default on if EDH_JEV_NO_COMMONS=1)")
    g.add_argument("--with-commons", action="store_true", help="override EDH_JEV_NO_COMMONS for one run")
    g.add_argument("--exclude-deck", help="skip cards already in this decklist")
    g.add_argument("--sort", default="edhrec", choices=["edhrec", "mv", "name", "random", "relevance", "newest"])
    g.add_argument("--limit", type=int, default=default_limit, help="max cards (0 = no limit)")
    g.add_argument("--include-illegal", action="store_true", help="include banned / not-legal cards")


def parse_mv(spec: str | None) -> tuple[float | None, float | None]:
    if not spec:
        return None, None
    s = spec.replace(" ", "")
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", s):
        return float(m.group(1)), float(m.group(2))
    if m := re.fullmatch(r"(<=|<|>=|>|=)?(\d+(?:\.\d+)?)", s):
        op, v = m.group(1) or "=", float(m.group(2))
        return {"<=": (None, v), "<": (None, v - 0.5), ">=": (v, None), ">": (v + 0.5, None), "=": (v, v)}[op]
    raise SystemExit(f"bad --mv {spec!r}")


def build_filters(args, db):
    from .deck import Deck
    from .search import Filters, ci_from_arg
    lo, hi = parse_mv(args.mv)
    exclude = set()
    if args.exclude_deck:
        d = Deck.load(args.exclude_deck)
        d.resolve(db)
        exclude = d.names()
    return Filters(
        ci_mask=ci_from_arg(db, args.ci), legal_only=not args.include_illegal, types=args.type,
        not_types=args.not_type, text=args.text, regex=args.regex, tags=args.tag, any_tags=args.any_tag,
        mv_min=lo, mv_max=hi, game_changers=args.gc, lands=args.lands, commander_able=args.commanders_only,
        exclude_names=exclude, min_edhrec_rank=args.min_rank, max_edhrec_rank=args.max_rank,
        released_after=args.after, sort=args.sort, limit=args.limit or None,
        exclude_rarities=["common"] if _skip_commons(args) else [],
    )


def _skip_commons(args) -> bool:
    if args.no_commons:
        return True
    if args.with_commons:
        return False
    if args.cmd == "jev":
        from .jev import env_flag
        return env_flag("EDH_JEV_NO_COMMONS")
    return False


def print_cards(cards, args) -> None:
    if getattr(args, "json", False):
        print(json.dumps([{"name": c.name, "mana_cost": c.mana_cost, "mv": c.cmc, "type": c.type_line, "text": c.text,
                           "ci": c.color_identity, "edhrec_rank": c.edhrec_rank, "game_changer": c.game_changer,
                           "tags": c.tags} for c in cards], indent=1))
    elif getattr(args, "names", False):
        print("\n".join(c.name for c in cards))
    else:
        w = getattr(args, "width", 200)
        for c in cards:
            gc = " [GC]" if c.game_changer else ""
            rank = f" #{c.edhrec_rank}" if c.edhrec_rank else ""
            print(f"{c.oneline(w)}{gc}{rank}")
    print(f"({len(cards)} cards)", file=sys.stderr)


# --------------------------------------------------------------------------- commands

def cmd_setup(args):
    from . import cards, tags
    ensure_dirs()
    print("downloading Scryfall oracle cards…", file=sys.stderr)
    bulk = cards.download_bulk(force=args.force)
    n = cards.build_db(bulk)
    print(f"card DB: {n} cards → {CARDS_DB}", file=sys.stderr)
    db = cards.CardDB()
    if args.force or not db.meta("tags_harvested_at"):
        print("harvesting Scryfall tagger role tags (~2-4 min)…", file=sys.stderr)
        tags.harvest()
    if args.forge:
        from . import forge
        forge.setup()
    cmd_doctor(args)


def cmd_doctor(args):
    from . import forge, jev
    ok = True
    if CARDS_DB.exists():
        from .cards import CardDB
        db = CardDB()
        age = (time.time() - CARDS_DB.stat().st_mtime) / 86400
        print(f"✓ card DB: {db.count()} cards, Scryfall data {db.meta('scryfall_updated_at') or '?'} ({age:.0f} days old)")
        th = db.meta("tags_harvested_at")
        print(f"{'✓' if th else '✗'} role tags: {'harvested ' + th if th else 'missing — run ./edh tags harvest'}")
        ok &= bool(th)
    else:
        print("✗ card DB missing — run ./edh setup")
        ok = False
    st = forge.status()
    print(f"{'✓' if st['java'] else '✗'} java: {st['java'] or 'not found (need JDK 17+)'}")
    print(f"{'✓' if st['jar'] else '✗'} Forge: {st['jar'] or 'not built — run ./edh forge setup (optional; needed for sims)'}")
    gs = {p.name: len(list(p.glob("*.dck"))) for p in sorted(GAUNTLET.glob("b*"))}
    gs = {k: v for k, v in gs.items() if v}
    listing = ", ".join(f"{k} ({v} decks)" for k, v in gs.items()) or "none — ./edh gauntlet build --bracket N"
    print(f"{'✓' if gs else '·'} gauntlets: {listing}")
    key = jev.load_api_key()
    print(f"{'✓' if key else '·'} Jev: {'TYPESAFE_API_KEY configured' if key else 'no TYPESAFE_API_KEY (semantic screening falls back to lexical; put key in .env)'}")
    return 0 if ok else 1


def cmd_cards_update(args):
    from . import cards
    n = cards.build_db(cards.download_bulk(force=True))
    print(f"card DB rebuilt: {n} cards (tags preserved)")


def cmd_tags(args):
    from . import tags
    if args.action == "harvest":
        tags.harvest(args.only or None)
    else:
        counts = tags.tag_counts() if CARDS_DB.exists() else {}
        for t, desc in tags.TAGS.items():
            print(f"{t:22s} {counts.get(t, 0):5d}  {desc}")


def cmd_card(args):
    from .cards import CardDB
    db = CardDB()
    for name in args.names:
        try:
            print(db.require(name).full())
        except KeyError as e:
            print(e)
        print()


def cmd_search(args):
    from .cards import CardDB
    from .search import pool
    db = CardDB()
    print_cards(pool(db, build_filters(args, db)), args)


def cmd_pool(args):
    from . import pool as P
    from .cards import CardDB
    from .search import ci_from_arg
    db = CardDB()
    if args.commander and not args.ci:
        args.ci = args.commander
    f = build_filters(args, db)
    cards = P.select(db, f, args.not_regex)
    cmdrs = [n.strip() for n in (args.commander or "").split("+") if n.strip()]
    incl, nd = P.inclusion_map(cmdrs, args.bracket) if cmdrs and not args.no_edhrec else ({}, 0)
    deck_names = set()
    if args.deck:
        from .deck import Deck
        deck_names = Deck.load(args.deck).names()
    if args.unlisted and incl:
        cards = [c for c in cards if c.name not in incl]
    if args.max_inclusion is not None and incl:
        cards = [c for c in cards if (incl.get(c.name) or 0) <= args.max_inclusion]
    title = args.title or " · ".join(x for x in (args.commander or args.ci, args.regex and f"/{args.regex}/",
                                                  args.text, " ".join(args.type)) if x)
    out = P.browse(cards, page=args.page, per_page=args.per_page, group=args.group, sort=args.order, incl=incl,
                   num_decks=nd, deck_names=deck_names, title=title)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        if args.all_pages:
            pages = max(1, -(-len(cards) // args.per_page))
            out = "\n\n".join(P.browse(cards, page=i, per_page=args.per_page, group=args.group, sort=args.order,
                                       incl=incl, num_decks=nd, deck_names=deck_names, title=title)
                               for i in range(1, pages + 1))
        Path(args.out).write_text(out + "\n")
        print(f"wrote {args.out} ({len(cards)} cards)")
    else:
        print(out)


def cmd_scry(args):
    from .cards import CardDB
    from .search import ci_from_arg, scryfall
    db = CardDB()
    cards = scryfall(db, args.query, ci_mask=ci_from_arg(db, args.ci), limit=args.limit,
                     legal_only=not args.include_illegal)
    print_cards(cards, args)


def _edhrec_inclusion(commander: str | None, db) -> dict[str, float]:
    if not commander:
        return {}
    from . import edhrec
    names = [db.require(n).name for n in re.split(r"\s*\+\s*", commander)]
    page = edhrec.commander_page(names)
    return {n: v["inclusion"] or 0.0 for n, v in page["cards"].items()}


def cmd_jev(args):
    from . import jev
    from .cards import CardDB
    from .search import pool
    db = CardDB()
    f = build_filters(args, db)
    if args.commander:  # never score the commander(s) as candidates for their own deck
        f.exclude_names |= {db.require(n).name for n in re.split(r"\s*\+\s*", args.commander)}
    cards = pool(db, f)
    if not cards:
        raise SystemExit("empty pool — loosen the filters")
    print(f"pool: {len(cards)} cards", file=sys.stderr)
    if args.action == "rank":
        brief = Path(args.brief).read_text()
        js, usage = jev.rank(cards, brief, dry_run=args.dry_run)
    else:
        ctx = Path(args.context).read_text() if args.context else ""
        js, usage = jev.grep(cards, args.requirement, context=ctx, dry_run=args.dry_run)
    if usage.get("dry_run"):
        print(json.dumps({k: v for k, v in usage.items() if k != "first_request"}, indent=1))
        req = usage["first_request"]
        preview = dict(req, questions=dict(list(req["questions"].items())[:2]))
        print("first request (2 of its questions shown):")
        print(json.dumps(preview, indent=1, ensure_ascii=False)[:6000])
        return
    incl = _edhrec_inclusion(args.commander, db)
    rows = []
    for j in js[: args.top]:
        c = j.card
        inc = incl.get(c.name)
        rows.append({"card": c.name, "value": round(j.value, 3), "confidence": j.confidence,
                     "edhrec_inclusion": inc, "edhrec_rank": c.edhrec_rank,
                     "gem": usage.get("provider") == "jev" and bool(incl) and (inc is None or inc < 0.05) and
                            (j.value >= (2.6 if args.action == "rank" else 0.75)),
                     "line": c.oneline(args.width)})
    if args.threshold is not None:
        rows = [r for r in rows if r["value"] >= args.threshold]
    for r in rows:
        inc = r["edhrec_inclusion"]
        tag = (" GEM" if r["gem"] else "") + (f" · {inc:.0%} of decks" if inc is not None else (" · not on EDHREC page" if incl else ""))
        conf = f" c{r['confidence']:.2f}" if r["confidence"] is not None else ""
        print(f"{r['value']:5.2f}{conf}{tag} | {r['line']}")
    if usage.get("provider") == "jev" and not usage.get("requests") and usage.get("cached"):
        print(f"(all {usage['cached']} answers served from the Jev cache — real Jev judgements, no new API calls)",
              file=sys.stderr)
    print(f"provider={usage.get('provider')} requests={usage.get('requests', 0)} cached={usage.get('cached', 0)} "
          f"input_tokens={usage.get('input_tokens', 0)} (~${usage.get('input_tokens', 0) / 1e6 * jev.PRICE_PER_MTOK:.3f})",
          file=sys.stderr)
    if usage.get("provider") == "lexical":
        print("NOTE: no TYPESAFE_API_KEY — this is keyword overlap, not semantic judgement. Read the pool yourself.",
              file=sys.stderr)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"usage": {k: v for k, v in usage.items() if k != "first_request"},
                                              "results": rows}, indent=1))


def cmd_edhrec(args):
    from . import edhrec
    from .cards import CardDB
    db = CardDB()
    names = [db.require(n).name for n in args.commander]
    page = edhrec.commander_page(names, args.bracket)
    if not page["found"]:
        print(f"no EDHREC page for {names} (slug {page['slug']})")
        return
    print(f"{' + '.join(names)} — {page['num_decks']} decks on EDHREC; brackets {page.get('bracket_counts')}")
    print("themes: " + ", ".join(f"{t} ({n})" for t, n in page["themes"]))
    rows = sorted(page["cards"].items(), key=lambda kv: -(kv[1]["inclusion"] or 0))
    print(f"\ntop {args.cards} cards by inclusion (synergy in brackets):")
    for n, v in rows[: args.cards]:
        print(f"  {v['inclusion'] or 0:4.0%} ({v['synergy'] or 0:+.2f})  {n}")
    hs = sorted(page["cards"].items(), key=lambda kv: -(kv[1]["synergy"] or 0))[:20]
    print("\nhighest synergy: " + "; ".join(f"{n} ({v['synergy']:+.2f})" for n, v in hs if v["synergy"]))


def _load(path, db):
    from .deck import load_resolved
    return load_resolved(path, db)


def cmd_deck(args):
    from .cards import CardDB
    from .deck import Deck
    db = CardDB()
    d = Deck.load(args.file)
    for c in args.commander or []:
        d.promote_commander(c)
    errs = d.resolve(db)
    if errs:
        print("\n".join(errs), file=sys.stderr)
    out = d.to_text()
    if args.write:
        Path(args.file).write_text(out)
        print(f"formatted {args.file} ({d.size()} cards)", file=sys.stderr)
    else:
        print(out)


def cmd_analyze(args):
    from . import analyze
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    print(analyze.summary(d))
    if not args.no_goldfish:
        print(analyze.goldfish(d, trials=args.trials).report())
        eng = _engine_reports(args.file, None, db, min(args.trials, 10000), quiet_missing=True)
        if eng:
            print(eng)


def _engine_reports(deck_file, brief, db, trials: int, quiet_missing: bool = False) -> str:
    from . import engine
    from .deck import Deck
    bp = Path(brief) if brief else Path(deck_file).resolve().parent / "brief.md"
    if not bp.exists():
        return "" if quiet_missing else f"no brief at {bp} (pass --brief)"
    specs = engine.parse(bp.read_text())
    if not specs:
        return "" if quiet_missing else (f"{bp} has no ```engine block: add one (see edhkit/engine.py) so the "
                                         "goldfish can test the deck's thesis")
    d = _load(deck_file, db)
    return "\n".join(engine.simulate(d, e, trials=trials).report() for e in specs)


def cmd_engine(args):
    from .cards import CardDB
    print(_engine_reports(args.file, args.brief, CardDB(), args.trials))


def cmd_audit(args):
    from . import deckaudit as A
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    folder = Path(args.file).resolve().parent
    notes_p = Path(args.notes) if args.notes else folder / "notes.md"
    notes = notes_p.read_text() if notes_p.exists() else ""
    kinds = ["omissions", "claims", "gems"] if args.kind == "all" else [args.kind]
    for kind in kinds:
        if kind == "omissions":
            rows = A.omissions(d, notes, args.bracket, args.min_inclusion)
            print(A.omissions_report(rows))
        elif kind == "claims":
            try:  # staples left out: lines explaining their absence get fact-checked too
                omitted = [db.require(r["name"]) for r in A.omissions(d, notes, args.bracket, args.min_inclusion)
                           if r["addressed"] and db.get(r["name"])]
            except Exception as e:  # EDHREC unreachable: check the deck's own cards only
                print(f"(omitted staples unavailable: {e}; checking deck cards only)")
                omitted = []
            rows = A.audit_claims(d, notes, db, model=args.model, effort=args.effort, omitted=omitted)
            print(A.claims_report(rows))
        else:
            brief_p = Path(args.brief) if args.brief else folder / "brief.md"
            rows = A.audit_gems(d, brief_p.read_text() if brief_p.exists() else "", db, model=args.model,
                                effort=args.effort, both_orders=not args.single_order)
            print(A.gems_report(rows))
        print(f"(saved {A.save(rows, args.file, kind)})\n")


def cmd_critical(args):
    from . import critical
    swap = dict(x.split("=", 1) for x in args.hand_swap)
    seeds = list(range(args.seed, args.seed + args.seeds))
    res = critical.run(Path(args.sim), args.game, args.turn, Path(args.deck), seeds, turns=args.turns,
                       strategist=args.strategist, hand_swap=swap, out_dir=Path(args.out) if args.out else None,
                       puzzle_only=args.puzzle)
    if args.puzzle:
        for r in res:
            print(r["puzzle"]); print("notes:", r["notes"])
        return
    alive = sum(r["alive"] for r in res)
    for r in res:
        print(f"seed {r['seed']}: {'ALIVE' if r['alive'] else 'DEAD '} at {r['our_life']} life; lost: "
              f"{', '.join(r['lost']) or '-'}; lives {r['life']}" + (f"; notes {r['notes']}" if r["notes"] else ""))
    print(f"survived {alive}/{len(res)}; mean life {sum(r['our_life'] for r in res) / len(res):.1f}")
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))


def cmd_goldfish(args):
    from . import analyze
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    print(analyze.goldfish(d, trials=args.trials, turns=args.turns).report())


def cmd_hands(args):
    from . import analyze
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    print(analyze.sample_hands(d, n=args.n, draws=args.draws, seed=args.seed))


def cmd_validate(args):
    from . import brackets
    from .cards import CardDB
    from .deck import Deck
    db = CardDB()
    d = Deck.load(args.file)
    r = brackets.validate(d, args.bracket, db, use_spellbook=not args.no_spellbook)
    print(json.dumps(r.as_dict(), indent=1) if args.json else r.text())
    return 0 if r.ok else 2


def cmd_forge(args):
    from . import forge
    if args.action == "setup":
        print(forge.setup(update=args.update))
    elif args.action == "build-pilot":
        print(forge.build_pilot(force=True))
    elif args.action == "index":
        print(len(forge.build_card_index(force=True)), "Forge cards indexed")
    elif args.action == "check":
        from .cards import CardDB
        db = CardDB()
        d = _load(args.file, db)
        print(json.dumps(forge.support_report(d), indent=1))
    else:
        print(json.dumps(forge.status(), indent=1))


def cmd_gauntlet(args):
    from . import gauntlet
    if args.action == "build":
        paths = gauntlet.build(args.bracket, count=args.count)
        print(f"{len(paths)} decks in {GAUNTLET / f'b{args.bracket}'}")
    else:
        for d in sorted(GAUNTLET.glob("b*")):
            idx = d / "index.json"
            meta = json.loads(idx.read_text()) if idx.exists() else []
            print(f"{d.name}: " + ", ".join(f"{m['commander']} [{m['color_identity']}]" for m in meta))


def _sim_outdir(args, deck_path: str) -> Path:
    if args.out:
        return Path(args.out)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path(deck_path).resolve().parent / "sims" / f"{stamp}-b{args.bracket}"


def _make_pilot(args, deck_path: str, outdir: Path):
    if getattr(args, "pilot", "forge") != "jev":
        return None
    from . import pilot
    folder = Path(deck_path).resolve().parent
    brief = Path(args.brief) if args.brief else folder / "brief.md"
    notes = folder / "notes.md"
    plan = pilot.deck_plan(brief, notes)
    return pilot.Pilot(plan, strategist=args.strategist, log_dir=outdir, sync=not args.async_strategist,
                       log_state=getattr(args, "log_state", False), version=args.strategist_version,
                       deck_path=Path(deck_path), effort=args.strategist_effort, verify=args.strategist_verify,
                       every=args.strategist_every, steer=args.steer, executor=args.executor,
                       executor_effort=args.executor_effort, game_log=args.game_log)


def cmd_scorecard(args):
    from . import scorecard
    scores = {}
    for path in args.paths:
        sim = Path(path)
        scores[sim.name or str(sim)] = sc = scorecard.score(sim)
        (sim / "scorecard.json").write_text(json.dumps(sc, indent=1))
    print(scorecard.report(scores))


def cmd_bugscan(args):
    from . import bugscan
    bugscan.main(args.paths, args.json, args.show)


def cmd_play(args):
    from . import play
    if args.show or args.verify:
        path = Path(args.show or args.verify)
        if args.show:
            print(play.show(path, all_passes=args.all))
        for g in play.verify(path):
            status = "OK" if g["ok"] else "MISMATCH"
            print(f"{status} {g['game']}: {g['decisions']} decisions; " + "; ".join(f"{k} {v}" for k, v in g["checks"].items()))
        return
    if not args.deck:
        raise SystemExit("usage: ./edh play <deck.txt> [--bracket 3]  |  ./edh play --show <session folder>")
    raise SystemExit(play.launch(Path(args.deck), args.bracket, Path(args.out) if args.out else None))


def cmd_scenario(args):
    from . import scenario
    scenario.main(args.state, args.deck, args.players, args.turns, args.seed)


def cmd_turn_audit(args):
    from . import turn_audit
    turn_audit.main(args.sim, args.deck, args.max, args.workers, args.out, args.dry)


def cmd_replay(args):
    from . import pilot, replay
    folder = Path(args.deck).resolve().parent
    plan = pilot.deck_plan(folder / "brief.md", folder / "notes.md")
    kinds = set(args.kinds.split(",")) if args.kinds else None
    res = replay.replay(Path(args.path), plan, kinds=kinds, limit=args.limit, seed=args.seed, steer=args.steer,
                        deck_path=Path(args.deck))
    print(replay.report(res))
    if args.judge and res["changed"]:
        from . import pilot_audit
        j = replay.judge(res, plan, args.judge, args.seed)
        res["judge"] = j
        print(pilot_audit.report(j).replace("pilot better", "new answer better").replace("Forge better", "old answer better"))
    if args.out:
        Path(args.out).write_text(json.dumps({k: v for k, v in res.items()}, indent=1, default=str))


def cmd_pilot_audit(args):
    from . import pilot, pilot_audit
    path = Path(args.path)
    log = path / "pilot_decisions.jsonl" if path.is_dir() else path
    folder = Path(args.deck).resolve().parent
    plan = pilot.deck_plan(folder / "brief.md", folder / "notes.md")
    kinds = set(args.kinds.split(",")) if args.kinds else None
    res = pilot_audit.audit(log, plan, n=args.n, seed=args.seed, model=pilot.STRATEGIST_MODEL,
                            effort=args.effort, workers=args.workers, kinds=kinds, hide_memo=args.hide_memo)
    if not res["sampled"]:
        raise SystemExit("no overrules with logged state; rerun the sim with --log-state")
    print(pilot_audit.report(res))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_sim(args):
    from . import forge
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    opps = forge.load_gauntlet(args.bracket, Path(args.pool) if args.pool else None)
    out = _sim_outdir(args, args.file)
    pilot = _make_pilot(args, args.file, out)
    s = forge.simulate(d, opps, db, games=args.games, pod_size=args.pod, games_per_pod=args.per_pod,
                       seed=args.seed, workers=args.workers, clock=args.clock, outdir=out, pilot=pilot,
                       count_decisions=getattr(args, "pilot", "forge") == "count")
    print(forge.report(s))
    print(f"logs + summary.json: {out}", file=sys.stderr)


def cmd_compare(args):
    from . import forge
    from .cards import CardDB
    db = CardDB()
    a, b = _load(args.a, db), _load(args.b, db)
    opps = forge.load_gauntlet(args.bracket, Path(args.pool) if args.pool else None)
    out = _sim_outdir(args, args.b)
    res = forge.compare(a, b, opps, db, games=args.games, pod_size=args.pod, games_per_pod=args.per_pod,
                        seed=args.seed, workers=args.workers, clock=args.clock, outdir=out)
    print("A:", forge.report(res["A"]))
    print("B:", forge.report(res["B"]))
    print(f"Δ win rate (B−A) {res['delta_win_rate']:+.1%} ± {res['approx_se']:.1%} → {res['verdict']}")


def cmd_diff(args):
    from collections import Counter
    from .cards import CardDB
    db = CardDB()
    a, b = _load(args.a, db), _load(args.b, db)
    ca = Counter({e.name: e.qty for e in a.commanders + a.main})
    cb = Counter({e.name: e.qty for e in b.commanders + b.main})
    added, removed = cb - ca, ca - cb
    print(f"+{sum(added.values())} / -{sum(removed.values())}")
    for n, q in sorted(removed.items()):
        print(f"- {q} {n}")
    for n, q in sorted(added.items()):
        print(f"+ {q} {n}")
    if args.proxies_out:
        Path(args.proxies_out).write_text("".join(f"{q} {n}\n" for n, q in sorted(added.items())))
        print(f"wrote added cards to {args.proxies_out}", file=sys.stderr)


def cmd_export(args):
    from . import export
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    if args.format == "pdf":
        out = Path(args.out or Path(args.file).with_suffix(".proxies.pdf"))
        export.pdf(d, out, paper=args.paper)
    elif args.format == "images":
        out = Path(args.out or Path(args.file).parent / "images")
        export.fetch_images(d, out)
        print(f"images in {out}")
    else:
        text = export.moxfield(d) if args.format == "moxfield" else export.plain(d)
        if args.out:
            Path(args.out).write_text(text)
        else:
            print(text, end="")


# --------------------------------------------------------------------------- parser

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="edh", description="Commander deckbuilding toolkit (see CLAUDE.md)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="download cards, build DB, harvest tags (+ --forge to build Forge)")
    s.add_argument("--force", action="store_true")
    s.add_argument("--forge", action="store_true", help="also clone + build Forge")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="what's installed / missing")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("cards", help="card DB maintenance")
    s.add_argument("action", choices=["update"])
    s.set_defaults(fn=cmd_cards_update)

    s = sub.add_parser("tags", help="role tags: list | harvest")
    s.add_argument("action", choices=["list", "harvest"], nargs="?", default="list")
    s.add_argument("--only", nargs="*")
    s.set_defaults(fn=cmd_tags)

    s = sub.add_parser("card", help="full details for one or more cards")
    s.add_argument("names", nargs="+")
    s.set_defaults(fn=cmd_card)

    for name, fn, helptext in (("search", cmd_search, "filter the local card DB"),):
        s = sub.add_parser(name, help=helptext)
        add_pool_args(s)
        s.add_argument("--json", action="store_true")
        s.add_argument("--names", action="store_true")
        s.add_argument("--width", type=int, default=200)
        s.set_defaults(fn=fn)

    s = sub.add_parser("pool", help="browse legal cards matching a pattern: full oracle text, paged, grouped, "
                                    "with this commander's EDHREC inclusion")
    add_pool_args(s, default_limit=0, default_lands="exclude")
    s.add_argument("--commander", help="commander name(s) joined with ' + ' (sets --ci and the EDHREC column)")
    s.add_argument("--bracket", type=int, help="EDHREC inclusion from this bracket's page")
    s.add_argument("--not-regex", help="drop cards whose rules text matches this regex (noise filter)")
    s.add_argument("--unlisted", action="store_true", help="only cards absent from the commander's EDHREC list")
    s.add_argument("--max-inclusion", type=float, help="only cards in at most this share of decks, e.g. 0.05")
    s.add_argument("--group", choices=["type", "mv", "none"], default="type")
    s.add_argument("--order", choices=["mv", "name", "edhrec", "newest"], default="mv", help="order within groups")
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--per-page", type=int, default=80)
    s.add_argument("--deck", help="mark cards already in this decklist")
    s.add_argument("--no-edhrec", action="store_true")
    s.add_argument("--title")
    s.add_argument("--out", help="write to a file instead of stdout")
    s.add_argument("--all-pages", action="store_true", help="with --out: write every page")
    s.set_defaults(fn=cmd_pool)

    s = sub.add_parser("scry", help="Scryfall-syntax search mapped onto the local DB")
    s.add_argument("query")
    s.add_argument("--ci")
    s.add_argument("--limit", type=int, default=200, help="max cards (0 = no limit; big result sets page slowly)")
    s.add_argument("--include-illegal", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--names", action="store_true")
    s.add_argument("--width", type=int, default=200)
    s.set_defaults(fn=cmd_scry)

    s = sub.add_parser("jev", help="semantic screening: rank (vs a strategy brief) | grep (vs a requirement)")
    jsub = s.add_subparsers(dest="action", required=True)
    r = jsub.add_parser("rank", help="score every card in the pool 0-4 for fit with a strategy brief")
    r.add_argument("--brief", required=True, help="markdown file describing the deck plan")
    g = jsub.add_parser("grep", help="P(card satisfies requirement) for every card in the pool")
    g.add_argument("requirement")
    g.add_argument("--context", help="optional brief file for deck context")
    for sp in (r, g):
        add_pool_args(sp, default_limit=0, default_lands="exclude")
        sp.add_argument("--top", type=int, default=150)
        sp.add_argument("--threshold", type=float)
        sp.add_argument("--commander", help="flag GEMs using this commander's EDHREC inclusion rates")
        sp.add_argument("--out", help="write JSON results here")
        sp.add_argument("--dry-run", action="store_true", help="show the request and cost estimate; no API call")
        sp.add_argument("--width", type=int, default=180)
        sp.set_defaults(fn=cmd_jev)

    s = sub.add_parser("edhrec", help="EDHREC baseline for a commander: themes, staples, synergy")
    s.add_argument("commander", nargs="+", help="one name, or two for partners")
    s.add_argument("--bracket", type=int, choices=range(1, 6))
    s.add_argument("--cards", type=int, default=60)
    s.set_defaults(fn=cmd_edhrec)

    s = sub.add_parser("deck", help="parse + normalise a decklist (groups by type, keeps # notes)")
    s.add_argument("file")
    s.add_argument("--write", action="store_true", help="rewrite the file in canonical form")
    s.add_argument("--commander", action="append", help="mark this card as commander (for pasted lists)")
    s.set_defaults(fn=cmd_deck)

    s = sub.add_parser("analyze", help="curve, colors, roles, game changers + goldfish")
    s.add_argument("file")
    s.add_argument("--trials", type=int, default=10000)
    s.add_argument("--no-goldfish", action="store_true")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("engine", help="engine goldfish: how often the deck assembles the engine its brief names")
    s.add_argument("file")
    s.add_argument("--brief", help="brief with ```engine blocks (default: brief.md next to the deck)")
    s.add_argument("--trials", type=int, default=10000)
    s.set_defaults(fn=cmd_engine)

    s = sub.add_parser("audit", help="deck audits: staples omitted, note claims vs oracle text, gems vs the staples "
                                     "they displaced")
    s.add_argument("kind", choices=["omissions", "claims", "gems", "all"])
    s.add_argument("file")
    s.add_argument("--bracket", type=int, help="omissions: EDHREC page for this bracket")
    s.add_argument("--min-inclusion", type=float, default=0.4, help="omissions: staple threshold (default 0.4)")
    s.add_argument("--notes", help="default: notes.md next to the deck")
    s.add_argument("--brief", help="gems: default brief.md next to the deck")
    s.add_argument("--model", default="claude-opus-5-5", help="claims/gems judge model")
    s.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    s.add_argument("--single-order", action="store_true", help="gems: judge each pair once (half the calls, noisier)")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("critical", help="replay a logged board (a lost game's turning point) over several seeds")
    s.add_argument("sim"); s.add_argument("game"); s.add_argument("turn", type=int)
    s.add_argument("--deck", required=True)
    s.add_argument("--seeds", type=int, default=3); s.add_argument("--seed", type=int, default=1)
    s.add_argument("--turns", type=int, default=5, help="turns to play after the logged one (5 = through our next turn)")
    s.add_argument("--strategist", default="claude-cli", choices=["claude-cli", "static"])
    s.add_argument("--hand-swap", action="append", default=[], metavar="OLD=NEW", help="replace a card in our hand")
    s.add_argument("--out", help="folder for per-run logs"); s.add_argument("--json")
    s.add_argument("--puzzle", action="store_true", help="print the puzzle only")
    s.set_defaults(fn=cmd_critical)

    s = sub.add_parser("goldfish", help="Monte Carlo mana/commander-timing simulation")
    s.add_argument("file")
    s.add_argument("--trials", type=int, default=20000)
    s.add_argument("--turns", type=int, default=10)
    s.set_defaults(fn=cmd_goldfish)

    s = sub.add_parser("hands", help="sample opening hands + next draws for eyeball review")
    s.add_argument("file")
    s.add_argument("-n", type=int, default=5)
    s.add_argument("--draws", type=int, default=3)
    s.add_argument("--seed", type=int)
    s.set_defaults(fn=cmd_hands)

    s = sub.add_parser("validate", help="legality + bracket check")
    s.add_argument("file")
    s.add_argument("--bracket", type=int, required=True, choices=range(1, 6))
    s.add_argument("--json", action="store_true")
    s.add_argument("--no-spellbook", action="store_true")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("forge", help="Forge engine: setup | status | index | check <deck> | build-pilot")
    s.add_argument("action", choices=["setup", "status", "index", "check", "build-pilot"])
    s.add_argument("file", nargs="?")
    s.add_argument("--update", action="store_true")
    s.set_defaults(fn=cmd_forge)

    s = sub.add_parser("gauntlet", help="opponent pools: build --bracket N | list")
    s.add_argument("action", choices=["build", "list"])
    s.add_argument("--bracket", type=int, choices=range(1, 6), default=3)
    s.add_argument("--count", type=int, default=12)
    s.set_defaults(fn=cmd_gauntlet)

    for name, fn in (("sim", cmd_sim), ("compare", cmd_compare)):
        s = sub.add_parser(name, help="Forge pods vs the bracket gauntlet" if name == "sim"
                           else "paired sim of two versions (same pods/seeds)")
        if name == "sim":
            s.add_argument("file")
        else:
            s.add_argument("a")
            s.add_argument("b")
        s.add_argument("--bracket", type=int, required=True, choices=range(1, 6))
        s.add_argument("--games", type=int, default=40)
        s.add_argument("--pod", type=int, default=4)
        s.add_argument("--per-pod", type=int, default=5, help="games per pod composition")
        s.add_argument("--workers", type=int)
        s.add_argument("--seed", type=int, default=1)
        s.add_argument("--clock", type=int, default=300, help="seconds before a game is called a draw")
        s.add_argument("--pool", help="directory of opponent decks (default gauntlet/b<bracket>)")
        s.add_argument("--out")
        if name == "sim":
            s.add_argument("--pilot", choices=["forge", "jev", "count"], default="forge",
                           help="who flies our seat: Forge's AI, the Jev executor (+ optional LLM strategist), or "
                                "'count' (Forge plays; every decision it makes for us is tallied)")
            s.add_argument("--strategist", choices=["static", "claude-cli", "anthropic"], default="static",
                           help="jev pilot only: who writes the per-turn strategy memo")
            s.add_argument("--brief", help="jev pilot only: deck plan file (default: brief.md next to the deck)")
            s.add_argument("--async-strategist", action="store_true",
                           help="don't pause the game for memos (real-time style); memos then lag the game")
            s.add_argument("--strategist-version", choices=["v2", "v3"], default="v3",
                           help="jev pilot only: v3 adds decklist by zone, card text, opponent dossiers, counted "
                                "mana and a win-path memo format")
            s.add_argument("--strategist-effort", choices=["low", "medium", "high"],
                           help="jev pilot only: strategist effort (default: low for v2, medium for v3)")
            s.add_argument("--strategist-verify", choices=["off", "low", "medium"], default="low",
                           help="jev pilot, v3 only: a second pass that audits each memo's mana, rules and targets "
                                "(beat unchecked memos 17-2 in blind A/B; adds ~20-60 s per memo)")
            s.add_argument("--strategist-every", type=int, default=1, metavar="K",
                           help="jev pilot only: plan every K-th of our turns (and on escalation); each memo then "
                                "covers K turns with a NEXT TURNS line. K=3 needs about a third of the strategist calls")
            s.add_argument("--steer", action="store_true",
                           help="jev pilot only: Forge's AI keeps the tactics and Jev overrules it only where the "
                                "memo asks for something Forge's answer lacks (aiming at its #1 threat, lethal, a held card, X or "
                                "held mana for a card it names), and plays the cards Forge's AI can't")
            s.add_argument("--executor", choices=["jev", "haiku", "sonnet"], default="jev",
                           help="jev pilot only: the model that answers each decision (haiku/sonnet use the API key "
                                "in EDH_ANTHROPIC_API_KEY, ANTHROPIC_API_KEY or .env, else claude -p)")
            s.add_argument("--executor-effort", choices=["low", "medium", "high"], default="medium",
                           help="jev pilot, haiku/sonnet executor: effort (thinking depth)")
            s.add_argument("--game-log", action="store_true",
                           help="jev pilot only: give the executor a round-by-round digest of the game so far")
            s.add_argument("--log-state", action="store_true",
                           help="jev pilot only: log full board + options per decision (needed by pilot-audit)")
        s.set_defaults(fn=fn)

    s = sub.add_parser("scorecard", help="execution scorecard of piloted sims, from their logs (no model calls); "
                                         "several runs side by side")
    s.add_argument("paths", nargs="+", help="sim --out folders")
    s.set_defaults(fn=cmd_scorecard)

    s = sub.add_parser("bugscan", help="invariant checks on sim logs: counters that fizzled, triggers that never "
                                       "fired, wasted mana, Forge-chosen trigger targets... (no model calls)")
    s.add_argument("paths", nargs="+", help="sim --out folders")
    s.add_argument("--json", help="write all findings here")
    s.add_argument("--show", type=int, default=4, help="findings shown per check (default 4)")
    s.set_defaults(fn=cmd_bugscan)

    s = sub.add_parser("play", help="play a deck yourself in Forge's desktop UI with every decision recorded "
                                    "(needs a display; run it on your own machine)")
    s.add_argument("deck", nargs="?", help="our deck.txt; the bracket's gauntlet decks are installed as opponents")
    s.add_argument("--bracket", type=int, default=3)
    s.add_argument("--out", help="session folder (default: <deck folder>/human/<timestamp>)")
    s.add_argument("--show", help="print a recorded session folder as one line per decision, then check it")
    s.add_argument("--all", action="store_true", help="with --show: include passes with nothing castable")
    s.add_argument("--verify", help="only check a recorded session against Forge's game log")
    s.set_defaults(fn=cmd_play)

    s = sub.add_parser("scenario", help="load one board (Forge puzzle syntax) into a real game and play it forward; "
                                        "reproduces a sim bug in seconds")
    s.add_argument("state", help="state file: p0battlefield=..., p0hand=..., activeplayer=p0, activephase=MAIN1 ...")
    s.add_argument("--deck", required=True, help="our deck (seat p0)")
    s.add_argument("--players", type=int, default=2)
    s.add_argument("--turns", type=int, default=1)
    s.add_argument("--seed", type=int, default=1)
    s.set_defaults(fn=cmd_scenario)

    s = sub.add_parser("turn-audit", help="a model reviews the turns that matter in a piloted run (bug-scan hits, "
                                          "win turns that didn't win, the end of losses) and reports defects by layer")
    s.add_argument("sim", help="sim --out folder (run with --log-state)")
    s.add_argument("--deck", required=True)
    s.add_argument("--max", type=int, default=40, help="turns to audit (default 40)")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--out", help="findings JSON (default <sim>/turn_audit.json, plus .md)")
    s.add_argument("--dry", action="store_true", help="list the turns that would be audited, no model calls")
    s.set_defaults(fn=cmd_turn_audit)

    s = sub.add_parser("replay", help="re-ask a piloted run's logged decisions under the current executor (Jev only); "
                                      "what changes, by kind, optionally blind-judged")
    s.add_argument("path", help="a sim --out folder run with --log-state")
    s.add_argument("--deck", required=True, help="the deck.txt that was piloted (for brief.md / notes.md)")
    s.add_argument("--kinds", help="comma-separated decision kinds to replay (default: all)")
    s.add_argument("--limit", type=int, default=0, help="replay a random sample of this many decisions")
    s.add_argument("--judge", type=int, default=0, help="blind-judge this many changed answers (Opus calls)")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--steer", action="store_true", help="replay under steer mode (Jev overrules only for memo-tagged reasons)")
    s.add_argument("--out", help="write the full result (changed decisions, judge) as JSON")
    s.set_defaults(fn=cmd_replay)

    s = sub.add_parser("pilot-audit", help="blind judge audit: were the Jev pilot's overrules better than Forge's picks?")
    s.add_argument("path", help="a sim --out folder or its pilot_decisions.jsonl (run with --log-state)")
    s.add_argument("--deck", required=True, help="the deck.txt that was piloted (for brief.md / notes.md)")
    s.add_argument("--n", type=int, default=60, help="overrules to sample")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    s.add_argument("--kinds", help="comma-separated decision kinds to audit (default: all)")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--hide-memo", action="store_true",
                   help="don't show the judge the strategist memo (the pilot follows it; this removes that bias)")
    s.add_argument("--out", help="write the full results as JSON")
    s.set_defaults(fn=cmd_pilot_audit)

    s = sub.add_parser("diff", help="cards added/removed between two lists (B relative to A)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--proxies-out", help="write just the added cards as a printable list")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("export", help="proxy-ready output: plain | moxfield | pdf | images")
    s.add_argument("file")
    s.add_argument("--format", choices=["plain", "moxfield", "pdf", "images"], default="plain")
    s.add_argument("--out")
    s.add_argument("--paper", choices=["letter", "a4"], default="letter")
    s.set_defaults(fn=cmd_export)

    args = p.parse_args(argv)
    try:
        rc = args.fn(args)
    except KeyError as e:
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
