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
    p = default_reports_dir()
    assert isinstance(p, Path)
    # On all three platforms platformdirs.user_documents_dir() ends with
    # "Documents". Reports dir is a subfolder named jakpost-reports.
    assert p.name == "jakpost-reports"
