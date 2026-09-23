"""Tiny HTTP layer: polite rate limiting, retries, and an on-disk JSON cache.

Scryfall asks for a descriptive User-Agent, an Accept header, and ~10 req/s max.
EDHREC and Commander Spellbook get the same courtesy.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .paths import CACHE

USER_AGENT = "edh-deckbuilder/0.1 (personal deckbuilding tool)"

_host_locks: dict[str, threading.Lock] = {}
_host_last: dict[str, float] = {}
_MIN_INTERVAL = {
    "api.scryfall.com": 0.11,
    "json.edhrec.com": 0.25,
    "backend.commanderspellbook.com": 0.25,
}


def _throttle(url: str) -> None:
    host = urllib.parse.urlparse(url).netloc
    gap = _MIN_INTERVAL.get(host)
    if not gap:
        return
    lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        wait = _host_last.get(host, 0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.monotonic()


def request(
    url: str,
    *,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60,
    retries: int = 4,
) -> bytes:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json;q=0.9,*/*;q=0.8"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    delay = 1.0
    for attempt in range(retries + 1):
        _throttle(url)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            retryable = e.code in (429, 500, 502, 503, 504, 529)
            if not retryable or attempt == retries:
                detail = e.read()[:500].decode(errors="replace")
                raise RuntimeError(f"HTTP {e.code} for {url}: {detail}") from e
            ra = e.headers.get("retry-after")
            time.sleep(float(ra) if ra and ra.replace(".", "").isdigit() else delay)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == retries:
                raise RuntimeError(f"network error for {url}: {e}") from e
            time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")


def get_json(url: str, **kw: Any) -> Any:
    return json.loads(request(url, **kw))


def post_json(url: str, body: Any, **kw: Any) -> Any:
    return json.loads(request(url, method="POST", body=body, **kw))


def cached_json(key: str, fetch, max_age_days: float = 7) -> Any:
    """Return fetch() result, cached on disk under data/cache/ for max_age_days."""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:80]
    path = CACHE / f"{safe}-{h}.json"
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400:
        return json.loads(path.read_text())
    value = fetch()
    path.write_text(json.dumps(value))
    return value


def download(url: str, dest: Path, timeout: float = 600) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
