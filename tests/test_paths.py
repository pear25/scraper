"""Tests for platform-default path resolution."""

from pathlib import Path

import pytest


def test_app_dirs_returns_platformdirs_object():
    from jakpost_scraper.paths import app_dirs
    pd = app_dirs()
    # platformdirs.PlatformDirs exposes user_config_dir, user_data_dir, etc.
    assert hasattr(pd, "user_config_dir")
    assert hasattr(pd, "user_data_dir")


def test_default_config_path_uses_app_name():
    from jakpost_scraper.paths import default_config_path
    p = default_config_path()
    assert isinstance(p, Path)
    assert p.name == "config.yaml"
    assert "jakpost-scraper" in str(p)


def test_default_data_dir_uses_app_name():
    from jakpost_scraper.paths import default_data_dir
    p = default_data_dir()
    assert isinstance(p, Path)
    assert "jakpost-scraper" in str(p)


def test_default_state_file_is_inside_data_dir():
    from jakpost_scraper.paths import default_data_dir, default_state_file
    state = default_state_file()
    assert state.parent == default_data_dir()
    assert state.name == "state.json"


def test_default_reports_dir_uses_documents_folder():
    from jakpost_scraper.paths import default_reports_dir
    import platformdirs
    p = default_reports_dir()
    assert isinstance(p, Path)
    assert p == Path(platformdirs.user_documents_dir()) / "jakpost-reports"


def test_resolve_config_path_prefers_explicit(tmp_path, monkeypatch):
    from jakpost_scraper.paths import resolve_config_path
    explicit = tmp_path / "x.yaml"
    explicit.write_text("")
    monkeypatch.setenv("JAKPOST_CONFIG", str(tmp_path / "ignored.yaml"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("")
    result = resolve_config_path(explicit_path=str(explicit))
    assert result == explicit


def test_resolve_config_path_uses_env_when_no_explicit(tmp_path, monkeypatch):
    from jakpost_scraper.paths import resolve_config_path
    env_path = tmp_path / "from_env.yaml"
    env_path.write_text("")
    monkeypatch.setenv("JAKPOST_CONFIG", str(env_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("")
    result = resolve_config_path(explicit_path=None)
    assert result == env_path


def test_resolve_config_path_uses_cwd_when_config_yaml_present(
        tmp_path, monkeypatch):
    from jakpost_scraper.paths import resolve_config_path
    monkeypatch.delenv("JAKPOST_CONFIG", raising=False)
    cwd_config = tmp_path / "config.yaml"
    cwd_config.write_text("")
    monkeypatch.chdir(tmp_path)
    result = resolve_config_path(explicit_path=None)
    assert result == cwd_config


def test_resolve_config_path_falls_back_to_platform_default(
        tmp_path, monkeypatch):
    from jakpost_scraper.paths import default_config_path, resolve_config_path
    monkeypatch.delenv("JAKPOST_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)  # no config.yaml in cwd
    result = resolve_config_path(explicit_path=None)
    assert result == default_config_path()


def test_resolve_data_dir_priority_order(tmp_path, monkeypatch):
    from jakpost_scraper.paths import default_data_dir, resolve_data_dir
    monkeypatch.delenv("JAKPOST_DATA_DIR", raising=False)
    # No explicit, no env -> platform default
    assert resolve_data_dir(explicit_path=None) == default_data_dir()
    # Env wins over default
    monkeypatch.setenv("JAKPOST_DATA_DIR", str(tmp_path / "envdata"))
    assert resolve_data_dir(explicit_path=None) == tmp_path / "envdata"
    # Explicit wins over env
    explicit = tmp_path / "explicit"
    assert resolve_data_dir(explicit_path=str(explicit)) == explicit


def test_resolve_reports_dir_priority_order(tmp_path, monkeypatch):
    from jakpost_scraper.paths import default_reports_dir, resolve_reports_dir
    monkeypatch.delenv("JAKPOST_REPORTS_DIR", raising=False)
    assert resolve_reports_dir(explicit_path=None) == default_reports_dir()
    monkeypatch.setenv("JAKPOST_REPORTS_DIR", str(tmp_path / "envreports"))
    assert resolve_reports_dir(explicit_path=None) == tmp_path / "envreports"
    explicit = tmp_path / "exp"
    assert resolve_reports_dir(explicit_path=str(explicit)) == explicit


def test_resolve_treats_empty_string_as_explicit_not_unset(tmp_path, monkeypatch):
    """An empty string must NOT be treated as 'no value' — None is the only
    sentinel for unset. This prevents Path('') from silently becoming Path('.')."""
    from jakpost_scraper.paths import (
        resolve_config_path, resolve_data_dir, resolve_reports_dir,
    )
    monkeypatch.setenv("JAKPOST_CONFIG", str(tmp_path / "from_env.yaml"))
    monkeypatch.setenv("JAKPOST_DATA_DIR", str(tmp_path / "from_env_data"))
    monkeypatch.setenv("JAKPOST_REPORTS_DIR", str(tmp_path / "from_env_reports"))
    # Explicit "" wins over the env vars — does NOT fall through.
    assert resolve_config_path(explicit_path="") == Path("")
    assert resolve_data_dir(explicit_path="") == Path("")
    assert resolve_reports_dir(explicit_path="") == Path("")


def test_ensure_default_config_writes_when_missing(tmp_path, monkeypatch):
    from jakpost_scraper.paths import (
        DEFAULT_CONFIG_YAML, ensure_default_config,
    )
    target = tmp_path / "config.yaml"
    written = ensure_default_config(target)
    assert written is True
    assert target.read_text() == DEFAULT_CONFIG_YAML
    assert target.parent.exists()


def test_ensure_default_config_no_op_when_present(tmp_path):
    from jakpost_scraper.paths import ensure_default_config
    target = tmp_path / "config.yaml"
    target.write_text("existing: 1\n")
    written = ensure_default_config(target)
    assert written is False
    assert target.read_text() == "existing: 1\n"


def test_ensure_default_config_creates_parent_dirs(tmp_path):
    from jakpost_scraper.paths import ensure_default_config
    target = tmp_path / "nested" / "deeper" / "config.yaml"
    written = ensure_default_config(target)
    assert written is True
    assert target.exists()
