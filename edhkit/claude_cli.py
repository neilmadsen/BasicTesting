"""One headless `claude -p` call, with failures treated as failures.

Every model call in the pilot and its tooling (strategist, verify pass, memo lab,
audit judge, dossiers) goes through here. A usage limit, an API error or a crash
comes back from `claude -p` as ordinary text on stdout, and once that text was
stored as a strategist memo: in one 24-game arm, 97 "memos" read "You've hit your
session limit", and the executor played 11 games guided by that sentence.
"""
from __future__ import annotations

import re
import subprocess
import tempfile

# Text that means the call failed, whatever the exit code says.
FAILURE = re.compile(r"^\s*(you've hit your (session|usage|weekly) limit|claude ai usage limit|usage limit reached|"
                     r"api error|error:|rate limit|credit balance is too low|invalid api key|"
                     r"please run /login|overloaded)", re.I)


class ClaudeCallFailed(RuntimeError):
    pass


def run(system: str, prompt: str, model: str, effort: str = "medium", timeout: int = 300) -> str:
    """The reply text; raises ClaudeCallFailed on a non-zero exit, empty output or a failure message."""
    try:
        out = subprocess.run(
            ["claude", "-p", "--tools", "", "--no-session-persistence", "--effort", effort,
             "--model", model, "--system-prompt", system],
            input=prompt, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired as e:
        raise ClaudeCallFailed(f"timed out after {timeout}s") from e
    text = out.stdout.strip()
    if out.returncode != 0 or not text or FAILURE.match(text):
        raise ClaudeCallFailed((text or out.stderr.strip() or f"exit {out.returncode}")[:200])
    return text
