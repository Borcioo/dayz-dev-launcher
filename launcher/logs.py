"""Locate DayZ log files and follow them like `tail -f`."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Iterator, Optional

# server-side log type -> glob pattern (searched in the server profiles dir)
SERVER_PATTERNS = {
    "script": "script_*.log",
    "rpt": "*.RPT",
    "adm": "*.ADM",
}
# the client writes its own script log into its own profiles dir
CLIENT_PATTERN = "script_*.log"

# full ordered set of log types the UI knows about
PATTERNS = {**SERVER_PATTERNS, "client": CLIENT_PATTERN}


def _newest(folder: Path, pattern: str) -> Optional[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        return None
    matches = list(folder.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def resolve(profiles_path, client_profiles_path=None) -> dict[str, Optional[Path]]:
    """Newest log per type. Server types come from ``profiles_path``; ``client``
    comes from ``client_profiles_path`` (falls back to the server dir when not
    given, e.g. in tests) so the client pane never mirrors the server's log."""
    server = Path(profiles_path)
    client = Path(client_profiles_path) if client_profiles_path else server
    result = {k: _newest(server, pat) for k, pat in SERVER_PATTERNS.items()}
    result["client"] = _newest(client, CLIENT_PATTERN)
    return result


def tail_lines(
    path, poll: float = 0.5, should_stop: Optional[Callable[[], bool]] = None,
    history: Optional[int] = None,
) -> Iterator[str]:
    """Yield existing lines, then follow appended lines. Waits if file absent.

    ``history``: how much of the pre-existing content to replay before
    following. ``None`` = all of it (full session, from line 1); an int = only
    the last N lines (avoids flooding the pane with a megabyte-sized RPT left
    over from a previous run).

    ``should_stop`` is polled on every idle tick (both while waiting for the
    file and between reads) so a long-running follower can be cancelled even
    when the log is quiet — without it, the generator blocks in ``sleep`` and
    a consuming worker thread would never exit.
    """
    path = Path(path)

    def _stop() -> bool:
        return should_stop is not None and should_stop()

    while not path.exists():
        if _stop():
            return
        time.sleep(poll)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        if history is not None:
            # consume to EOF keeping only the last N lines, then follow
            from collections import deque
            for line in deque(fh, maxlen=history):
                if _stop():
                    return
                yield line.rstrip("\n")
        buffer = ""
        while True:
            if _stop():
                return
            chunk = fh.readline()
            if chunk:
                buffer += chunk
                if buffer.endswith("\n"):
                    yield buffer.rstrip("\n")
                    buffer = ""
            else:
                if buffer:
                    yield buffer.rstrip("\n")
                    buffer = ""
                time.sleep(poll)


def last_lines(path, n: int) -> list:
    """Return the last n lines of a file (one-shot, no follow). [] if absent."""
    from collections import deque
    p = Path(path)
    if not p.is_file():
        return []
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        return [ln.rstrip("\n") for ln in deque(fh, maxlen=n)]
