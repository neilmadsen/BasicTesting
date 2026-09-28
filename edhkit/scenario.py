"""Scenario runs: load one board into a real Forge game and play it forward a turn or two.

    ./edh scenario state.txt --deck decks/vivi-ornitier/edhrec-b3/deck.txt [--players 2] [--turns 1]

The state file is Forge's puzzle syntax: `p0battlefield=Vivi Ornitier|Id:1;Ophidian Eye|AttachedTo:1`,
`p0hand=Opt`, `activeplayer=p0`, `activephase=MAIN1`, `turn=5`, `p1life=40`... p0 plays --deck, the other
seats play gauntlet decks (only their libraries matter unless the state names their zones). Prints the game log.
A bug found in a 40-minute sim becomes a scenario that reproduces it in seconds, then a regression test.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import forge
from .cards import CardDB
from .deck import Deck


def run(state: str, deck: Path, players: int = 2, turns: int = 1, seed: int = 1, pilot_seat: int | None = None,
        sidecar: str | None = None, opponents: list[Path] | None = None) -> list[str]:
    jar = forge.find_jar()
    pilot = forge.build_pilot()
    db = CardDB()
    idx = forge.build_card_index()
    opps = opponents or forge.load_gauntlet(3)
    decks = [forge._load_any_deck(deck, db)] + [forge._load_any_deck(p, db) for p in opps[:players - 1]]
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        paths = []
        for i, d in enumerate(decks):
            text, _ = forge.forge_deck_text(d, f"P{i + 1}", idx)
            p = home / f"P{i + 1}.dck"
            p.write_text(text)
            paths.append(str(p))
        sp = home / "state.txt"
        sp.write_text(state)
        cmd = ["java", f"-Xmx{forge.JAVA_XMX}", f"-Duser.home={home}", "-Djava.awt.headless=true",
               "-cp", f"{jar}:{pilot}", "edh.pilot.ScenarioMain", "--state", str(sp), "--turns", str(turns),
               "--seed", str(seed)]
        if pilot_seat:
            cmd += ["--pilot-seat", str(pilot_seat), "--sidecar", sidecar or "none"]
        out = subprocess.run(cmd + paths, cwd=forge.res_dir(), capture_output=True, text=True, timeout=300)
    lines = [ln for ln in out.stdout.splitlines() if ln and not ln.startswith("Picked up JAVA_TOOL_OPTIONS")]
    if out.returncode and not lines:
        raise RuntimeError(out.stderr[-2000:])
    return lines


class ScriptedSidecar:
    """A stand-in for the pilot sidecar: `rules(req)` returns {question id: option id} for each request (missing
    ids keep Forge's choice). Every request is kept in `.requests`, so a test can check what the pilot was asked
    and what it was offered."""

    def __init__(self, rules: Callable[[dict], dict] | None = None):
        self.rules = rules or (lambda req: {})
        self.requests: list[dict] = []
        me = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                me.requests.append(req)
                try:
                    answers = me.rules(req) or {}
                except Exception as e:  # a broken rule keeps Forge's choices, like the real sidecar
                    print(f"[scripted sidecar] {e}")
                    answers = {}
                data = json.dumps({"answers": answers}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()


def pick(q: dict, contains: str) -> str | None:
    """The id of the first option in question q whose text contains `contains`."""
    return next((o["id"] for o in q["options"] if contains in o["text"]), None)


def main(state_path: str, deck: str, players: int, turns: int, seed: int) -> None:
    for line in run(Path(state_path).read_text(), Path(deck), players, turns, seed):
        print(line)
