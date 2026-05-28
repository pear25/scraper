"""Phase banners and per-item progress lines, all on stderr."""

import sys
import time
from contextlib import contextmanager


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def progress(done: int, total: int, message: str) -> None:
    log(f"  [{done}/{total}] {message}")


@contextmanager
def phase(name: str):
    """Print a start/end banner around a block and report elapsed time.

    Yields a dict the caller can populate with a 'summary' string that will be
    appended to the end banner — e.g. "46 ok / 1 failed".
    """
    log(f"====== Start {name} ======")
    started = time.monotonic()
    state: dict = {}
    try:
        yield state
    finally:
        elapsed = time.monotonic() - started
        suffix = f", {state['summary']}" if state.get("summary") else ""
        log(f"====== End {name} ({elapsed:.1f}s{suffix}) ======")
