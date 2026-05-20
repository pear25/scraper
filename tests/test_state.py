from datetime import datetime, timezone

import pytest

from jakpost_scraper.state import State, StateError, load_state, save_state, prune_seen


def test_load_missing_file_is_first_run(tmp_path):
    state = load_state(str(tmp_path / "state.json"))
    assert state.last_run_at is None
    assert state.seen_urls == {}


def test_save_then_load_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    original = State(
        last_run_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        seen_urls={"https://example.com/a.html":
                   datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)},
    )
    save_state(path, original)
    loaded = load_state(path)
    assert loaded.last_run_at == original.last_run_at
    assert loaded.seen_urls == original.seen_urls


def test_corrupt_file_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not valid json")
    with pytest.raises(StateError):
        load_state(str(path))


def test_prune_seen_drops_old_entries():
    now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    state = State(
        last_run_at=now,
        seen_urls={
            "https://example.com/old.html": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "https://example.com/new.html": datetime(2026, 5, 19, tzinfo=timezone.utc),
        },
    )
    prune_seen(state, retention_days=30, now=now)
    assert "https://example.com/old.html" not in state.seen_urls
    assert "https://example.com/new.html" in state.seen_urls


def test_save_is_atomic_leaves_no_temp_files(tmp_path):
    path = str(tmp_path / "state.json")
    save_state(path, State())
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "state.json"]
    assert leftovers == []
