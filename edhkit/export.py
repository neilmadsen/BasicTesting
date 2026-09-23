"""Proxy-ready exports.

  plain    — "1 Card Name" lines, commanders first. Pastes into Moxfield, Archidekt,
             MPCFill, mtgprint.net, and most proxy printers.
  moxfield — same, with a Commander section header Moxfield's importer understands.
  pdf      — print-ready 3×3 sheets at true card size (63×88 mm) from Scryfall scans,
             with light cut guides. Double-faced cards get both faces.
  images   — the card images themselves, for uploading to a print service.
"""

from __future__ import annotations

import struct
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import net
from .deck import Deck
from .paths import CACHE

PAGE_SIZES = {"letter": (612.0, 792.0), "a4": (595.28, 841.89)}
CARD_W, CARD_H = 63 / 25.4 * 72, 88 / 25.4 * 72  # points


def plain(deck: Deck) -> str:
    return deck.to_plain()


def moxfield(deck: Deck) -> str:
    lines = ["Commander"] + [f"{e.qty} {e.name}" for e in deck.commanders] + ["", "Deck"]
    lines += [f"{e.qty} {e.name}" for e in sorted(deck.main, key=lambda e: e.name)]
    return "\n".join(lines) + "\n"


def _image_jobs(deck: Deck) -> list[tuple[str, str, int]]:
    jobs = []
    for e in deck.commanders + deck.main:
        c = e.card
        if not c or not c.image_front:
            continue
        jobs.append((c.image_front, f"{c.oracle_id}-front.jpg", e.qty))
        if c.image_back:
            jobs.append((c.image_back, f"{c.oracle_id}-back.jpg", e.qty))
    return jobs


def fetch_images(deck: Deck, dest: Path | None = None) -> list[tuple[Path, int]]:
    cache = CACHE / "images"
    cache.mkdir(parents=True, exist_ok=True)
    jobs = _image_jobs(deck)

    def get(job):
        url, fn, qty = job
        p = cache / fn
        if not p.exists():
            net.download(url, p)
        return p, qty

    with ThreadPoolExecutor(max_workers=6) as ex:
        paths = list(ex.map(get, jobs))
    if dest:
        dest.mkdir(parents=True, exist_ok=True)
        for (p, _), job, e in zip(paths, jobs, range(len(jobs))):
            (dest / f"{e + 1:03d}-{p.name}").write_bytes(p.read_bytes())
    return paths


def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    raise ValueError("not a JPEG")


def pdf(deck: Deck, out: Path, paper: str = "letter", bleed_guides: bool = True) -> Path:
    imgs = fetch_images(deck)
    cards: list[Path] = []
    for p, qty in imgs:
        cards += [p] * qty
    pw, ph = PAGE_SIZES[paper]
    mx, my = (pw - 3 * CARD_W) / 2, (ph - 3 * CARD_H) / 2
    objs: list[bytes] = []

    def add(obj: bytes) -> int:
        objs.append(obj)
        return len(objs)

    img_ids: dict[Path, int] = {}
    for p in dict.fromkeys(cards):
        data = p.read_bytes()
        w, h = _jpeg_size(data)
        img_ids[p] = add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                         b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (w, h, len(data))
                         + data + b"\nendstream")
    pages_id_placeholder = len(objs) + 1
    add(b"")  # Pages, filled below
    page_ids = []
    for start in range(0, len(cards), 9):
        chunk = cards[start:start + 9]
        ops = []
        res = []
        for k, p in enumerate(chunk):
            col, row = k % 3, k // 3
            x = mx + col * CARD_W
            y = ph - my - (row + 1) * CARD_H
            ops.append(f"q {CARD_W:.2f} 0 0 {CARD_H:.2f} {x:.2f} {y:.2f} cm /Im{img_ids[p]} Do Q")
            res.append(f"/Im{img_ids[p]} {img_ids[p]} 0 R")
        if bleed_guides:
            ops.append("0.6 G 0.3 w")
            for c in range(4):
                x = mx + c * CARD_W
                ops.append(f"{x:.2f} {my - 12:.2f} m {x:.2f} {my - 2:.2f} l S {x:.2f} {ph - my + 2:.2f} m {x:.2f} {ph - my + 12:.2f} l S")
            for r in range(4):
                y = my + r * CARD_H
                ops.append(f"{mx - 12:.2f} {y:.2f} m {mx - 2:.2f} {y:.2f} l S {pw - mx + 2:.2f} {y:.2f} m {pw - mx + 12:.2f} {y:.2f} l S")
        content = zlib.compress("\n".join(ops).encode())
        cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content) + content + b"\nendstream")
        pid = add(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
                   "/Resources << /XObject << %s >> >> >>" % (pages_id_placeholder, pw, ph, cid, " ".join(res))).encode())
        page_ids.append(pid)
    objs[pages_id_placeholder - 1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (
        " ".join(f"{i} 0 R" for i in page_ids), len(page_ids))).encode()
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id_placeholder)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, o in enumerate(objs, 1):
            offsets.append(f.tell())
            f.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
        xref = f.tell()
        f.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
        for off in offsets:
            f.write(b"%010d 00000 n \n" % off)
        f.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref))
    print(f"wrote {out} ({len(cards)} card faces, {len(page_ids)} pages, {paper})", file=sys.stderr)
    return out
