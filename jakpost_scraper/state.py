"""Persistent run state: last-run timestamp and the seen-URL set."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import dt_to_iso, iso_to_dt, to_utc


class StateError(Exception):
    """Raised when an existing state file cannot be parsed."""


@dataclass
class State:
    last_run_at: datetime | None = None
    seen_urls: dict[str, datetime] = field(default_factory=dict)


def load_state(path: str) -> State:
    """Load state from path. A missing file is a valid first run."""
    if not os.path.exists(path):
        return State()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        last = data.get("last_run_at")
        seen = {
            entry["url"]: iso_to_dt(entry["seen_at"])
            for entry in data.get("seen_urls", [])
        }
        return State(
            last_run_at=iso_to_dt(last) if last else None,
            seen_urls=seen,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise StateError(f"Cannot parse state file {path}: {e}") from e


def save_state(path: str, state: State) -> None:
    """Write state to path atomically (temp file + rename)."""
    data = {
        "last_run_at": dt_to_iso(state.last_run_at) if state.last_run_at else None,
        "seen_urls": [
            {"url": url, "seen_at": dt_to_iso(seen_at)}
            for url, seen_at in sorted(state.seen_urls.items())
        ],
    }
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def prune_seen(state: State, retention_days: int, now: datetime) -> None:
    """Drop seen-URL entries older than retention_days (mutates state)."""
    cutoff = to_utc(now) - timedelta(days=retention_days)
    state.seen_urls = {
        url: seen_at
        for url, seen_at in state.seen_urls.items()
        if to_utc(seen_at) >= cutoff
    }
