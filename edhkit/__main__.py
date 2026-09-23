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
    )


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


def cmd_sim(args):
    from . import forge
    from .cards import CardDB
    db = CardDB()
    d = _load(args.file, db)
    opps = forge.load_gauntlet(args.bracket, Path(args.pool) if args.pool else None)
    out = _sim_outdir(args, args.file)
    s = forge.simulate(d, opps, db, games=args.games, pod_size=args.pod, games_per_pod=args.per_pod,
                       seed=args.seed, workers=args.workers, clock=args.clock, outdir=out)
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

    s = sub.add_parser("scry", help="Scryfall-syntax search mapped onto the local DB")
    s.add_argument("query")
    s.add_argument("--ci")
    s.add_argument("--limit", type=int, default=200)
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

    s = sub.add_parser("forge", help="Forge engine: setup | status | index | check <deck>")
    s.add_argument("action", choices=["setup", "status", "index", "check"])
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
        s.set_defaults(fn=fn)

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
