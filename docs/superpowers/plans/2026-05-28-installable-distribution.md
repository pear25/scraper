# Installable Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `jakpost-scraper` as a PyPI package installable on macOS, Linux, and Windows via a single `curl | sh` (or PowerShell `irm | iex`) one-liner, with platform-default config/state/data/reports paths so the global command works from any directory.

**Architecture:** Publish the existing Python package to PyPI. Thin install scripts (`install.sh`, `install.ps1`) at repo root install `uv` (Astral's standalone tool installer — handles Python 3.11+ download itself) and run `uv tool install jakpost-scraper`. Inside the package, add `platformdirs`-based path resolution to `config.py` with order: CLI flag > env var > cwd > platform default. CLI gains `--config`, `--data-dir`, `--reports-dir`, and `--upgrade`/`--update` flags. A tag-triggered GitHub Actions workflow runs tests, builds, and publishes to PyPI.

**Tech Stack:** Python 3.11+, `platformdirs`, `uv` (tool installer), PyPI, GitHub Actions, POSIX shell, PowerShell 5.1+.

**Spec:** [docs/superpowers/specs/2026-05-28-installable-distribution-design.md](../specs/2026-05-28-installable-distribution-design.md)

---

## File Structure

**Created:**
- `install.sh` — POSIX installer (Mac/Linux).
- `install.ps1` — PowerShell installer (Windows).
- `LICENSE` — MIT license text.
- `.github/workflows/release.yml` — tag-triggered release workflow.
- `jakpost_scraper/paths.py` — new module: platform-default path resolution. Keeps `config.py` focused on YAML parsing/validation.
- `tests/test_paths.py` — tests for `paths.py`.

**Modified:**
- `pyproject.toml` — add `platformdirs`, tighten metadata, keep `version = "0.1.0"`.
- `jakpost_scraper/config.py` — `data_dir`/`reports_dir`/`state_file` default to `None`; `load_config` resolves them via `paths.py`.
- `jakpost_scraper/cli.py` — add `--config`, `--data-dir`, `--reports-dir`, `--upgrade`/`--update` flags; use `paths.resolve_config_path()` instead of hardcoded `CONFIG_PATH = "config.yaml"`.
- `tests/test_config.py` — extend for new resolution paths.
- `tests/test_cli.py` — extend for new flags.
- `README.md` — lead with the one-liner install; document new flags and config locations.

**Why `paths.py` as a new file:** path resolution mixes platform detection, env var reads, cwd checks, and file creation. Wedging that into `config.py` would push it past its current focused purpose (YAML loading + validation). A small dedicated module keeps both files easy to hold in your head and easy to test in isolation.

---

## Task 1: Add `platformdirs` dependency and tighten `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml**

Run: `cat pyproject.toml`

Expected current contents — verify before editing:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "jakpost-scraper"
version = "0.1.0"
description = "Scrape and summarize The Jakarta Post articles"
requires-python = ">=3.11"
dependencies = [
    "httpx",
    "beautifulsoup4",
    "lxml",
    "python-dateutil",
    "pyyaml",
    "python-dotenv",
    "claude-agent-sdk",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-httpx"]

[project.scripts]
jakpost-scrape = "jakpost_scraper.cli:cli_entry"

[tool.setuptools]
packages = ["jakpost_scraper"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Replace pyproject.toml with the tightened version**

Write this exact content:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "jakpost-scraper"
version = "0.1.0"
description = "Scrape and summarize articles from The Jakarta Post"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
authors = [
    { name = "Pierson Lim", email = "piersonlimas12@gmail.com" },
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: Text Processing",
]
dependencies = [
    "httpx",
    "beautifulsoup4",
    "lxml",
    "python-dateutil",
    "pyyaml",
    "python-dotenv",
    "platformdirs",
    "claude-agent-sdk",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-httpx"]

[project.urls]
Homepage = "https://github.com/pear25/scraper"
Repository = "https://github.com/pear25/scraper"
Issues = "https://github.com/pear25/scraper/issues"

[project.scripts]
jakpost-scrape = "jakpost_scraper.cli:cli_entry"

[tool.setuptools]
packages = ["jakpost_scraper"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Install the new dependency into the dev venv and verify**

Run: `python -m pip install -e ".[dev]"`
Expected: installs `platformdirs` plus the existing deps; no errors.

Run: `python -c "import platformdirs; print(platformdirs.__version__)"`
Expected: prints a version number (e.g. `4.x.x`).

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

Run: `python -m pytest`
Expected: PASS (same count as before the change; the metadata edits don't touch runtime).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add platformdirs dep and tighten PyPI metadata"
```

---

## Task 2: Add MIT LICENSE file

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Write the LICENSE file**

Create `LICENSE` with this exact content (replace nothing; this is the standard MIT text):

```
MIT License

Copyright (c) 2026 Pierson Lim

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "docs: add MIT LICENSE"
```

---

## Task 3: Create `paths.py` — platform path constants

**Files:**
- Create: `jakpost_scraper/paths.py`
- Test: `tests/test_paths.py`

Build `paths.py` in layers. Task 3 covers the platform-default constants only. Task 4 adds the resolution logic. Task 5 adds first-run config writing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_paths.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.paths'`.

- [ ] **Step 3: Create `jakpost_scraper/paths.py` with the constants**

```python
"""Platform-default paths for installed CLI usage.

Resolution order (highest priority first) is implemented in `resolve_*`
functions: CLI flag > env var > cwd (if config.yaml exists) > platform
default. The constants in this module describe only the platform-default
layer.
"""

from functools import lru_cache
from pathlib import Path

import platformdirs

APP_NAME = "jakpost-scraper"
REPORTS_FOLDER_NAME = "jakpost-reports"


@lru_cache(maxsize=1)
def app_dirs() -> platformdirs.PlatformDirs:
    """Return the PlatformDirs instance for this app. Cached."""
    return platformdirs.PlatformDirs(APP_NAME)


def default_config_path() -> Path:
    """Platform-default location for config.yaml."""
    return Path(app_dirs().user_config_dir) / "config.yaml"


def default_data_dir() -> Path:
    """Platform-default location for state.json, articles/, summaries/."""
    return Path(app_dirs().user_data_dir)


def default_state_file() -> Path:
    """Platform-default location for state.json (lives inside the data dir)."""
    return default_data_dir() / "state.json"


def default_reports_dir() -> Path:
    """Platform-default location for the generated Markdown reports.

    Lives under the user's Documents folder so reports are easy to find,
    rather than buried in an app-data directory."""
    return Path(platformdirs.user_documents_dir()) / REPORTS_FOLDER_NAME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_paths.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/paths.py tests/test_paths.py
git commit -m "feat(paths): platform-default path constants via platformdirs"
```

---

## Task 4: Add `resolve_*` functions to `paths.py`

**Files:**
- Modify: `jakpost_scraper/paths.py`
- Modify: `tests/test_paths.py`

- [ ] **Step 1: Add failing tests for the resolution logic**

Append to `tests/test_paths.py`:

```python
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
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `pytest tests/test_paths.py -v -k resolve`
Expected: FAIL — `ImportError: cannot import name 'resolve_config_path' from 'jakpost_scraper.paths'`.

- [ ] **Step 3: Add the resolution functions to `paths.py`**

Append to `jakpost_scraper/paths.py`:

```python
import os

ENV_CONFIG = "JAKPOST_CONFIG"
ENV_DATA_DIR = "JAKPOST_DATA_DIR"
ENV_REPORTS_DIR = "JAKPOST_REPORTS_DIR"


def resolve_config_path(explicit_path: str | None) -> Path:
    """Resolve the config.yaml path.

    Order: explicit CLI flag > JAKPOST_CONFIG env > cwd/config.yaml if it
    exists > platform default. Returns the chosen Path even if it doesn't
    exist on disk (load_config decides what to do with that).
    """
    if explicit_path:
        return Path(explicit_path)
    env = os.environ.get(ENV_CONFIG)
    if env:
        return Path(env)
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config
    return default_config_path()


def resolve_data_dir(explicit_path: str | None) -> Path:
    """Resolve the data directory. Order: explicit > env > platform default.

    Note: there is no cwd fallback for data — only config.yaml triggers
    cwd-mode (so config.yaml living next to the project drags state/data
    along with it; see resolve_state_file and resolve_data_dir_for_config)."""
    if explicit_path:
        return Path(explicit_path)
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env)
    return default_data_dir()


def resolve_reports_dir(explicit_path: str | None) -> Path:
    """Resolve the reports directory. Order: explicit > env > platform default."""
    if explicit_path:
        return Path(explicit_path)
    env = os.environ.get(ENV_REPORTS_DIR)
    if env:
        return Path(env)
    return default_reports_dir()
```

- [ ] **Step 4: Run all path tests to verify they pass**

Run: `pytest tests/test_paths.py -v`
Expected: PASS — all 11 tests green.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/paths.py tests/test_paths.py
git commit -m "feat(paths): add resolve_* functions with CLI/env/cwd/default order"
```

---

## Task 5: First-run config-writing helper

**Files:**
- Modify: `jakpost_scraper/paths.py`
- Modify: `tests/test_paths.py`

When the chosen config path doesn't exist on disk AND it's the platform default (not user-supplied), write a default `config.yaml` there so first-run users have something to read and edit.

- [ ] **Step 1: Embed the default config text as a module constant**

Append to `jakpost_scraper/paths.py`:

```python
DEFAULT_CONFIG_YAML = """\
# Jakarta Post scraper configuration. All keys are optional; defaults shown.
sections: all              # "all" or a list of section identifiers
summary_mode: both         # per-article | digest | both
model: claude-haiku-4-5    # Claude model for summarization
paywall: keep-teaser       # keep-teaser | skip
request_delay: 1.0         # seconds between HTTP requests
concurrency: 4             # max concurrent article fetches / summary calls
lookback_buffer_minutes: 20
seen_url_retention_days: 30
http_timeout: 15           # seconds
http_retries: 3            # attempts per request

# Authenticated scraping (optional; off by default).
# Set JAKPOST_EMAIL and JAKPOST_PASSWORD environment variables to use it.
# auth_enabled: false
# auth_login_url: "https://www.thejakartapost.com/user/account/login"
"""
```

This is the current `config.yaml` content minus `data_dir`/`reports_dir`/`state_file` — those three are now resolved by `paths.py`, so we no longer want them in the shipped default (their presence in the file would override the platform defaults).

- [ ] **Step 2: Write the failing test**

Append to `tests/test_paths.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_paths.py::test_ensure_default_config_writes_when_missing -v`
Expected: FAIL — `ImportError: cannot import name 'ensure_default_config'`.

- [ ] **Step 4: Implement `ensure_default_config`**

Append to `jakpost_scraper/paths.py`:

```python
def ensure_default_config(path: Path) -> bool:
    """Write the shipped default config to `path` if it doesn't exist.

    Returns True if a file was written, False if one already existed.
    Creates parent directories as needed."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_YAML)
    return True
```

- [ ] **Step 5: Run path tests to verify they pass**

Run: `pytest tests/test_paths.py -v`
Expected: PASS — all 14 tests green.

- [ ] **Step 6: Commit**

```bash
git add jakpost_scraper/paths.py tests/test_paths.py
git commit -m "feat(paths): ensure_default_config writes shipped defaults on first run"
```

---

## Task 6: Update `Config` defaults to `None` for resolvable paths

**Files:**
- Modify: `jakpost_scraper/config.py`
- Modify: `tests/test_config.py`

`data_dir`, `reports_dir`, `state_file` need to default to `None` so `load_config` can tell "user didn't set this; resolve a platform default" apart from "user explicitly set this string". The actual resolution happens in Task 7.

- [ ] **Step 1: Add failing test for the new defaults**

Append to `tests/test_config.py`:

```python
def test_path_defaults_are_none_before_resolution():
    """data_dir/reports_dir/state_file should default to None so load_config
    can distinguish unset from explicitly set."""
    cfg = Config()
    assert cfg.data_dir is None
    assert cfg.reports_dir is None
    assert cfg.state_file is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_path_defaults_are_none_before_resolution -v`
Expected: FAIL — `cfg.data_dir == "./data"`, not None.

- [ ] **Step 3: Change the dataclass defaults in `config.py`**

In [jakpost_scraper/config.py](jakpost_scraper/config.py), replace lines 28-30:

```python
    data_dir: str = "./data"
    reports_dir: str = "./reports"
    state_file: str = "./state.json"
```

with:

```python
    data_dir: str | None = None      # resolved by paths.resolve_data_dir
    reports_dir: str | None = None   # resolved by paths.resolve_reports_dir
    state_file: str | None = None    # resolved by paths.resolve_state_file
```

Also update the type hints — search the file for any other usages of `cfg.data_dir`/`cfg.reports_dir`/`cfg.state_file` that assume non-None. There are none in `config.py` itself; that's a Task 7 concern.

- [ ] **Step 4: Run config tests to verify the new test passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS for all tests including the new one. The existing `test_defaults_when_no_file` doesn't assert path values, so nothing else breaks here.

- [ ] **Step 5: Confirm the full suite still passes (path-using code is exercised by integration tests)**

Run: `python -m pytest`
Expected: Most tests pass. **`tests/test_integration.py` and any test that calls `write_articles_json`/`write_summaries_json`/`write_markdown_report`/`save_state` against a real Config WILL fail** because `os.path.join(None, ...)` raises `TypeError`.

Note which tests fail. They will all be fixed in Task 7 when `load_config` starts resolving the defaults. Do NOT try to fix them in this task.

- [ ] **Step 6: Commit (red state, intentional)**

```bash
git add jakpost_scraper/config.py tests/test_config.py
git commit -m "refactor(config): path fields default to None pending resolution"
```

The next task makes the suite green again.

---

## Task 7: Wire `load_config` to resolve paths via `paths.py`

**Files:**
- Modify: `jakpost_scraper/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add failing tests for resolution behavior in `load_config`**

Append to `tests/test_config.py`:

```python
def test_load_config_fills_in_platform_defaults_when_unset(tmp_path, monkeypatch):
    """When YAML omits paths and CLI overrides them, load_config falls back
    to the platform defaults from paths.py."""
    from jakpost_scraper.paths import (
        default_data_dir, default_reports_dir, default_state_file,
    )
    monkeypatch.delenv("JAKPOST_DATA_DIR", raising=False)
    monkeypatch.delenv("JAKPOST_REPORTS_DIR", raising=False)
    yaml = tmp_path / "config.yaml"
    yaml.write_text("summary_mode: digest\n")
    cfg = load_config(str(yaml), {})
    assert cfg.data_dir == str(default_data_dir())
    assert cfg.reports_dir == str(default_reports_dir())
    assert cfg.state_file == str(default_state_file())


def test_load_config_yaml_path_overrides_default(tmp_path, monkeypatch):
    monkeypatch.delenv("JAKPOST_DATA_DIR", raising=False)
    yaml = tmp_path / "config.yaml"
    yaml.write_text("data_dir: /tmp/mydata\n")
    cfg = load_config(str(yaml), {})
    assert cfg.data_dir == "/tmp/mydata"


def test_load_config_cli_override_wins(tmp_path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text("data_dir: /tmp/yamlpath\n")
    cfg = load_config(str(yaml), {"data_dir": "/tmp/cli_path"})
    assert cfg.data_dir == "/tmp/cli_path"


def test_load_config_env_var_used_when_yaml_silent(tmp_path, monkeypatch):
    monkeypatch.setenv("JAKPOST_DATA_DIR", "/tmp/from_env")
    yaml = tmp_path / "config.yaml"
    yaml.write_text("")
    cfg = load_config(str(yaml), {})
    assert cfg.data_dir == "/tmp/from_env"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v -k load_config`
Expected: FAIL — `cfg.data_dir is None`, not the resolved path.

- [ ] **Step 3: Update `load_config` to call resolvers after YAML+CLI merge**

In [jakpost_scraper/config.py](jakpost_scraper/config.py), update the imports at top:

```python
"""Configuration: defaults, YAML file, and CLI overrides."""

import os
from dataclasses import dataclass, fields

import yaml

from . import paths

SUMMARY_MODES = ("per-article", "digest", "both")
PAYWALL_MODES = ("keep-teaser", "skip")
```

Then in `load_config`, after the `Config(**values)` line and before `validate_config(cfg)`, insert resolution:

```python
def load_config(config_path: str | None, cli_overrides: dict) -> Config:
    """Build a Config from defaults, an optional YAML file, then CLI overrides.

    After merging, fill in any unset path fields (data_dir, reports_dir,
    state_file) from paths.resolve_* — which honors env vars and platform
    defaults. CLI overrides and YAML values both win over the resolver.
    """
    values: dict = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise ConfigError(f"{config_path} must contain a YAML mapping")
        values.update(loaded)

    known = {f.name for f in fields(Config)}
    for key in values:
        if key not in known:
            raise ConfigError(f"Unknown config key: {key}")

    values.update({k: v for k, v in cli_overrides.items() if v is not None})
    cfg = Config(**values)

    # Resolve path fields: anything still None gets the env/default treatment.
    if cfg.data_dir is None:
        cfg.data_dir = str(paths.resolve_data_dir(explicit_path=None))
    if cfg.reports_dir is None:
        cfg.reports_dir = str(paths.resolve_reports_dir(explicit_path=None))
    if cfg.state_file is None:
        cfg.state_file = str(paths.default_state_file())

    validate_config(cfg)
    return cfg
```

- [ ] **Step 4: Run all tests to confirm green**

Run: `python -m pytest`
Expected: PASS — the new tests pass, AND the integration tests broken in Task 6 are now green again because resolved string paths flow through `write_articles_json` etc.

If any integration test still fails, it's because it creates a `Config` directly (not via `load_config`) and passes it to a write function. Those tests must construct paths explicitly — they already do, by passing `tmp_path` strings. Read the failure carefully before changing anything.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/config.py tests/test_config.py
git commit -m "feat(config): resolve unset path fields via paths.resolve_*"
```

---

## Task 8: Add `--config`, `--data-dir`, `--reports-dir` CLI flags

**Files:**
- Modify: `jakpost_scraper/cli.py`
- Modify: `tests/test_cli.py`

The CLI must accept explicit path overrides and use them when resolving the config file location, and pass them through to `cli_overrides` so `load_config` honors them.

- [ ] **Step 1: Write failing tests for the parser flags**

Append to `tests/test_cli.py`:

```python
def test_config_flag_parses():
    args = build_parser().parse_args(["--config", "/tmp/c.yaml"])
    assert args.config == "/tmp/c.yaml"


def test_data_dir_flag_parses():
    args = build_parser().parse_args(["--data-dir", "/tmp/d"])
    assert args.data_dir == "/tmp/d"


def test_reports_dir_flag_parses():
    args = build_parser().parse_args(["--reports-dir", "/tmp/r"])
    assert args.reports_dir == "/tmp/r"


def test_path_flags_default_to_none():
    args = build_parser().parse_args([])
    assert args.config is None
    assert args.data_dir is None
    assert args.reports_dir is None


def test_cli_overrides_passes_through_path_flags():
    args = build_parser().parse_args(
        ["--data-dir", "/tmp/d", "--reports-dir", "/tmp/r"])
    overrides = cli_overrides(args)
    assert overrides["data_dir"] == "/tmp/d"
    assert overrides["reports_dir"] == "/tmp/r"


def test_cli_overrides_omits_unset_path_flags():
    args = build_parser().parse_args([])
    overrides = cli_overrides(args)
    assert "data_dir" not in overrides
    assert "reports_dir" not in overrides
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "config_flag or data_dir or reports_dir"`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'config'` (or similar).

- [ ] **Step 3: Add the flags to `build_parser`**

In [jakpost_scraper/cli.py](jakpost_scraper/cli.py), add three new arguments inside `build_parser`. Place them right after the `--since` argument and before `--dry-run` so help output groups them with other input/output options:

```python
    parser.add_argument("--config",
                        help="Path to config.yaml (overrides env JAKPOST_CONFIG "
                             "and platform default)")
    parser.add_argument("--data-dir",
                        help="Directory for state.json + articles/ + summaries/ "
                             "(overrides env JAKPOST_DATA_DIR and platform default)")
    parser.add_argument("--reports-dir",
                        help="Directory for Markdown reports (overrides env "
                             "JAKPOST_REPORTS_DIR and platform default)")
```

- [ ] **Step 4: Update `cli_overrides` to forward path flags to load_config**

Replace `cli_overrides` in `cli.py` with:

```python
def cli_overrides(args: argparse.Namespace) -> dict:
    """Extract config overrides (summary_mode, sections, auth, paths) from
    parsed args. None values are filtered out by load_config so unset flags
    don't clobber YAML/env values."""
    overrides: dict = {}
    if args.summary_mode is not None:
        overrides["summary_mode"] = args.summary_mode
    if args.sections is not None:
        overrides["sections"] = [s.strip() for s in args.sections.split(",")
                                 if s.strip()]
    if args.auth is not None:
        overrides["auth_enabled"] = args.auth
    if args.data_dir is not None:
        overrides["data_dir"] = args.data_dir
    if args.reports_dir is not None:
        overrides["reports_dir"] = args.reports_dir
    return overrides
```

- [ ] **Step 5: Update `main()` to resolve the config path before calling load_config**

In `main()`, replace these lines:

```python
    args = build_parser().parse_args(argv)
    try:
        config = load_config(CONFIG_PATH, cli_overrides(args))
```

with:

```python
    args = build_parser().parse_args(argv)
    try:
        from . import paths
        config_path = paths.resolve_config_path(args.config)
        # First-run UX: if the resolved path doesn't exist and it's the
        # platform default, write the shipped default config there.
        if (not config_path.exists()
                and config_path == paths.default_config_path()):
            if paths.ensure_default_config(config_path):
                print(f"Wrote default config to {config_path}",
                      file=sys.stderr)
        config = load_config(str(config_path), cli_overrides(args))
```

Then delete the now-unused module constant near the top of the file:

```python
CONFIG_PATH = "config.yaml"
```

- [ ] **Step 6: Run CLI tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS — including the 6 new tests.

- [ ] **Step 7: Run full suite**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add jakpost_scraper/cli.py tests/test_cli.py
git commit -m "feat(cli): --config, --data-dir, --reports-dir override flags"
```

---

## Task 9: Add `--upgrade`/`--update` flag

**Files:**
- Modify: `jakpost_scraper/cli.py`
- Modify: `tests/test_cli.py`

When the user passes `--upgrade` or `--update`, print the upgrade command and exit 0 without running a scrape.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_upgrade_flag_parses():
    args = build_parser().parse_args(["--upgrade"])
    assert args.upgrade is True


def test_update_alias_parses():
    args = build_parser().parse_args(["--update"])
    assert args.upgrade is True


def test_upgrade_default_false():
    args = build_parser().parse_args([])
    assert args.upgrade is False


def test_main_with_upgrade_prints_command_and_exits_zero(capsys):
    from jakpost_scraper.cli import main
    rc = main(["--upgrade"])
    assert rc == 0
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "uv tool upgrade jakpost-scraper" in out
    assert "install.sh" in out
    assert "install.ps1" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "upgrade or update"`
Expected: FAIL — `--upgrade` not recognized.

- [ ] **Step 3: Add the flag to `build_parser`**

In [jakpost_scraper/cli.py](jakpost_scraper/cli.py), add inside `build_parser` (place after `--reset-state`):

```python
    parser.add_argument("--upgrade", "--update", dest="upgrade",
                        action="store_true",
                        help="Print the upgrade command and exit (does not run "
                             "a scrape)")
```

- [ ] **Step 4: Handle the flag in `main` before any other work**

Add a constant at module level (near top, after imports):

```python
UPGRADE_MESSAGE = """\
To upgrade jakpost-scraper, run:

  uv tool upgrade jakpost-scraper

Or re-run the installer:
  macOS/Linux:  curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
  Windows:      irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
"""
```

Then add this block to `main()` right after `args = build_parser().parse_args(argv)`, before the `try:`:

```python
    if args.upgrade:
        print(UPGRADE_MESSAGE)
        return 0
```

- [ ] **Step 5: Run upgrade tests**

Run: `pytest tests/test_cli.py -v -k "upgrade or update"`
Expected: PASS — all 4 new tests green.

- [ ] **Step 6: Run full suite**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add jakpost_scraper/cli.py tests/test_cli.py
git commit -m "feat(cli): --upgrade flag prints upgrade command and exits"
```

---

## Task 10: Write `install.sh`

**Files:**
- Create: `install.sh`

The POSIX installer is straight shell — no test harness in this repo for shell scripts. Validate by running it locally after writing.

- [ ] **Step 1: Create `install.sh`**

```sh
#!/bin/sh
# jakpost-scraper installer for macOS and Linux.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
set -eu

APP_NAME="jakpost-scraper"
CMD_NAME="jakpost-scrape"
UV_INSTALLER_URL="https://astral.sh/uv/install.sh"

note()   { printf '%s\n' "$1"; }
header() { printf '\n=== %s ===\n' "$1"; }
warn()   { printf '\033[33m%s\033[0m\n' "$1" >&2; }
fail()   { printf '\033[31mError: %s\033[0m\n' "$1" >&2; exit 1; }

header "Checking prerequisites"
if ! command -v curl >/dev/null 2>&1; then
    fail "curl is required but not found. Install curl and re-run."
fi
note "curl: ok"

header "Installing uv (Python tool manager)"
if command -v uv >/dev/null 2>&1; then
    note "uv: already installed ($(uv --version))"
else
    note "Installing uv from $UV_INSTALLER_URL ..."
    curl -LsSf "$UV_INSTALLER_URL" | sh
    # uv's installer puts the binary in ~/.local/bin or ~/.cargo/bin and
    # updates the user's shell rc files; expose it to THIS shell so the
    # next step finds it.
    if [ -d "$HOME/.local/bin" ]; then
        PATH="$HOME/.local/bin:$PATH"
    fi
    if [ -d "$HOME/.cargo/bin" ]; then
        PATH="$HOME/.cargo/bin:$PATH"
    fi
    export PATH
    if ! command -v uv >/dev/null 2>&1; then
        fail "uv installed but not on PATH. Open a new shell and re-run."
    fi
    note "uv: installed ($(uv --version))"
fi

header "Installing $APP_NAME"
uv tool install --upgrade "$APP_NAME"

header "Checking for the claude CLI (used for summarization)"
if command -v claude >/dev/null 2>&1; then
    note "claude: found ($(command -v claude))"
    CLAUDE_MISSING=0
else
    warn "claude CLI not found."
    warn "Summarization needs the claude CLI installed and authenticated."
    warn "Install: https://docs.claude.com/en/docs/claude-code/quickstart"
    warn "Without it, run jakpost-scrape with --no-summary."
    CLAUDE_MISSING=1
fi

header "Detecting config location"
OS_KERNEL=$(uname -s)
case "$OS_KERNEL" in
    Darwin)
        CONFIG_PATH="$HOME/Library/Application Support/$APP_NAME/config.yaml"
        ;;
    Linux)
        CONFIG_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME/config.yaml"
        ;;
    *)
        CONFIG_PATH="(see jakpost-scrape --help for path resolution)"
        ;;
esac

header "Install complete"
note ""
note "Command:  $CMD_NAME"
note "Config:   $CONFIG_PATH"
note "          (written automatically on first run)"
note ""
note "Try:      $CMD_NAME --help"
if [ "$CLAUDE_MISSING" -eq 1 ]; then
    note "          $CMD_NAME --no-summary           # works without claude CLI"
fi
note ""
note "Upgrade:  $CMD_NAME --upgrade"
note ""
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x install.sh`

- [ ] **Step 3: Lint the script**

Run: `sh -n install.sh`
Expected: no output (syntactically valid POSIX shell).

If `shellcheck` is available locally, also run: `shellcheck install.sh`
Expected: clean (no warnings). If unavailable, skip.

- [ ] **Step 4: Dry-run the relevant logic without actually installing**

Test only the prerequisites check by running the first ~10 lines manually — don't pipe the whole script into `sh` yet, since you don't want to actually publish before this works end-to-end.

Run:
```bash
sh -c 'set -eu; if ! command -v curl >/dev/null 2>&1; then echo missing; else echo ok; fi'
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "feat(install): POSIX installer (macOS, Linux) via uv"
```

End-to-end testing of the installer happens after PyPI publish (Task 14).

---

## Task 11: Write `install.ps1`

**Files:**
- Create: `install.ps1`

- [ ] **Step 1: Create `install.ps1`**

```powershell
# jakpost-scraper installer for Windows (PowerShell 5.1+).
# Usage:
#   irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$AppName  = 'jakpost-scraper'
$CmdName  = 'jakpost-scrape'
$UvInstallerUrl = 'https://astral.sh/uv/install.ps1'

function Write-Header($text) {
    Write-Host ""
    Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Write-Warn($text) {
    Write-Host $text -ForegroundColor Yellow
}

function Fail($text) {
    Write-Host "Error: $text" -ForegroundColor Red
    exit 1
}

Write-Header "Checking prerequisites"
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "PowerShell 5.1 or newer is required."
}
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

Write-Header "Installing uv (Python tool manager)"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "uv: already installed ($(& uv --version))"
} else {
    Write-Host "Installing uv from $UvInstallerUrl ..."
    Invoke-RestMethod $UvInstallerUrl | Invoke-Expression
    # uv installs to %USERPROFILE%\.local\bin and updates the User PATH.
    # Make it visible to this session so the next step finds it.
    $userLocalBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path $userLocalBin) {
        $env:PATH = "$userLocalBin;$env:PATH"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv installed but not on PATH. Open a new PowerShell and re-run."
    }
    Write-Host "uv: installed ($(& uv --version))"
}

Write-Header "Installing $AppName"
& uv tool install --upgrade $AppName
if ($LASTEXITCODE -ne 0) {
    Fail "uv tool install failed (exit $LASTEXITCODE)."
}

Write-Header "Checking for the claude CLI (used for summarization)"
$claude = Get-Command claude -ErrorAction SilentlyContinue
$claudeMissing = $false
if ($claude) {
    Write-Host "claude: found ($($claude.Source))"
} else {
    Write-Warn "claude CLI not found."
    Write-Warn "Summarization needs the claude CLI installed and authenticated."
    Write-Warn "Install: https://docs.claude.com/en/docs/claude-code/quickstart"
    Write-Warn "Without it, run jakpost-scrape with --no-summary."
    $claudeMissing = $true
}

Write-Header "Detecting config location"
$configPath = Join-Path $env:APPDATA "$AppName\config.yaml"

Write-Header "Install complete"
Write-Host ""
Write-Host "Command:  $CmdName"
Write-Host "Config:   $configPath"
Write-Host "          (written automatically on first run)"
Write-Host ""
Write-Host "Try:      $CmdName --help"
if ($claudeMissing) {
    Write-Host "          $CmdName --no-summary           # works without claude CLI"
}
Write-Host ""
Write-Host "Upgrade:  $CmdName --upgrade"
Write-Host ""
```

- [ ] **Step 2: Syntax-check the script**

If PowerShell is available locally:
Run: `pwsh -NoProfile -Command "[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw install.ps1), [ref]\$null) | Out-Null; Write-Host 'ok'"`
Expected: `ok` printed, no exceptions.

If PowerShell isn't installed locally, skip — Task 14's manual verification will catch syntax errors on the Windows test machine.

- [ ] **Step 3: Commit**

```bash
git add install.ps1
git commit -m "feat(install): PowerShell installer (Windows) via uv"
```

---

## Task 12: Add `.github/workflows/release.yml`

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the workflow directory and file**

```bash
mkdir -p .github/workflows
```

Then create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # needed for creating a GitHub Release
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python 3.11
        run: uv python install 3.11

      - name: Install dev dependencies
        run: uv sync --extra dev

      - name: Run tests
        run: uv run pytest

      - name: Build sdist and wheel
        run: uv build

      - name: Publish to PyPI
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
        run: uv publish

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.whl
            dist/*.tar.gz
          generate_release_notes: true
```

Note on `uv sync --extra dev`: this requires `uv.lock` to exist. The repo currently uses `pip install -e ".[dev]"`. If `uv sync` fails on first CI run because there's no lockfile, replace the two lines:

```yaml
      - name: Install dev dependencies
        run: uv sync --extra dev
```

with:

```yaml
      - name: Install package and dev dependencies
        run: uv pip install --system -e ".[dev]"
```

Pick the second form if you don't want to commit a `uv.lock` to the repo.

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo ok`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: tag-triggered release workflow (tests, build, PyPI, GH Release)"
```

The workflow won't fire until you push a `v*` tag (Task 14), and won't publish until the `PYPI_API_TOKEN` secret is configured. Both are covered in Task 14.

---

## Task 13: Update README to lead with the install one-liner

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the README**

Replace `README.md` entirely with this content. The existing content's structure changes significantly — install one-liner first, dev-from-source last.

```markdown
# Jakarta Post Scraper & Summarizer

A command-line tool that discovers articles published on
[The Jakarta Post](https://www.thejakartapost.com) since the last run,
scrapes their full text, summarizes them with Claude, and writes JSON files
plus a Markdown report.

## Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
```

The installer downloads [`uv`](https://github.com/astral-sh/uv) (a small
standalone tool that handles Python for you), then installs `jakpost-scrape`
into an isolated environment and puts it on your PATH. No prior Python
install required.

**Optional — summarization:** install the
[`claude` CLI](https://docs.claude.com/en/docs/claude-code/quickstart) and
run `claude login`. The scraper works without it if you pass `--no-summary`.

## Usage

```bash
jakpost-scrape                       # scrape since last run (24h on first run)
jakpost-scrape --dry-run             # list what would be scraped
jakpost-scrape --no-summary          # scrape only, skip summarization
jakpost-scrape --since 48h           # override the window (also accepts ISO dates)
jakpost-scrape --summary-mode digest # per-article | digest | both
jakpost-scrape --console-output article-text # print title + URL + raw body to stdout
jakpost-scrape --limit 5             # cap article count
jakpost-scrape --sections business   # restrict sections
jakpost-scrape --upgrade             # print the upgrade command
```

## Configuration file locations

The first time you run `jakpost-scrape`, it writes a default `config.yaml`
under your OS's standard app-config directory:

| OS      | Config                                                      | State + data                                     | Reports                                    |
|---------|-------------------------------------------------------------|--------------------------------------------------|--------------------------------------------|
| macOS   | `~/Library/Application Support/jakpost-scraper/config.yaml` | `~/Library/Application Support/jakpost-scraper/` | `~/Documents/jakpost-reports/`             |
| Linux   | `~/.config/jakpost-scraper/config.yaml`                     | `~/.local/share/jakpost-scraper/`                | `~/Documents/jakpost-reports/`             |
| Windows | `%APPDATA%\jakpost-scraper\config.yaml`                     | `%APPDATA%\jakpost-scraper\`                     | `%USERPROFILE%\Documents\jakpost-reports\` |

You can override any path:

- `--config PATH`, `--data-dir DIR`, `--reports-dir DIR` — per-run.
- `JAKPOST_CONFIG`, `JAKPOST_DATA_DIR`, `JAKPOST_REPORTS_DIR` — environment.
- If `config.yaml` exists in your current directory, the tool uses it
  (preserves the "run from a project folder" workflow).

Resolution order: CLI flag > env var > cwd > platform default.

## How it works

1. Reads `state.json` for the last-run timestamp (first run looks back 24h).
2. Walks The Jakarta Post's Google News sitemaps to find articles in the window.
3. Scrapes each article's full text (paywalled articles yield the teaser).
4. Summarizes via the Claude Agent SDK (`per-article`, `digest`, or `both`).
5. Writes `<data-dir>/articles/<run-id>.json`,
   `<data-dir>/summaries/<run-id>.json`, and `<reports-dir>/<run-id>.md`,
   then advances `state.json`.

`--console-output article-text` keeps those file outputs and also writes
each scraped article to stdout with its title, URL, and raw body text.

See `docs/superpowers/specs/2026-05-20-jakpost-scraper-design.md` for the
full design.

## Upgrading

```bash
jakpost-scrape --upgrade       # prints the upgrade command
uv tool upgrade jakpost-scraper
```

Or re-run the installer one-liner — it's idempotent.

## Uninstalling

```bash
uv tool uninstall jakpost-scraper
```

This removes the command. Config, state, and reports stay where they are —
delete those directories manually if you want a clean wipe.

## Authenticated scraping (premium articles)

By default the scraper runs as a guest, so premium articles return only a
teaser. To capture full premium article bodies, log in with your own Jakarta
Post account.

Set credentials in environment variables:

```bash
export JAKPOST_EMAIL=you@example.com
export JAKPOST_PASSWORD=your-password
```

Then enable in `config.yaml` (`auth_enabled: true`) or pass `--auth` on a
single run. The scraper logs in over HTTP on first use and caches the
session, reusing it on later runs. When the session expires, the run aborts
with a message — re-run with `--reauth` to log in again.

Authentication is opt-in: with `auth_enabled: false` (the default) the
scraper behaves as a guest.

## Develop from source

```bash
git clone https://github.com/pear25/scraper.git jakpost-scraper
cd jakpost-scraper
python -m pip install -e ".[dev]"
python -m pytest
jakpost-scrape --help
```

When run from a directory containing `config.yaml`, the tool reads that
local file and writes state/data/reports under that directory — matching
the development workflow.
```

- [ ] **Step 2: Verify the README renders sanely**

Run: `head -40 README.md`
Expected: shows the new title, install commands, no truncation.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: lead with install one-liner, document new flags + config paths"
```

---

## Task 14: First PyPI release and end-to-end verification

This task is **manual** — it touches external systems (PyPI, GitHub, fresh installs). Do not script these steps; do them one at a time and confirm each.

**Files:**
- Modify: none (release flow only)

- [ ] **Step 1: Create a PyPI account and project token**

1. Visit https://pypi.org/account/register/ if you don't already have an account.
2. Verify your email.
3. Visit https://pypi.org/manage/account/token/ and create an API token. Name it `github-actions-jakpost-scraper`. Scope: select "Entire account" for the first release (PyPI requires this until the project exists). After the first release, generate a project-scoped token and replace it.
4. Copy the token (`pypi-AgEI...`). It's shown only once.

- [ ] **Step 2: Store the token as a GitHub secret**

```bash
gh secret set PYPI_API_TOKEN --repo pear25/scraper
# Paste the token when prompted, then Enter.
```

Verify: `gh secret list --repo pear25/scraper` shows `PYPI_API_TOKEN`.

- [ ] **Step 3: Confirm the build works locally**

Run from the repo root:
```bash
uv build
ls dist/
```
Expected: `dist/jakpost_scraper-0.1.0-py3-none-any.whl` and `dist/jakpost_scraper-0.1.0.tar.gz` exist.

If `uv` isn't installed locally:
```bash
python -m pip install build
python -m build
ls dist/
```
Expected: same two files.

Clean up: `rm -rf dist/` (CI rebuilds them).

- [ ] **Step 4: Merge the branch and tag the release**

```bash
# Merge feat/pip-install into main via PR or directly, your preference.
git checkout main
git pull
git merge --no-ff feat/pip-install
git push origin main

git tag v0.1.0
git push origin v0.1.0
```

- [ ] **Step 5: Watch the workflow**

```bash
gh run watch --repo pear25/scraper
```

Expected: workflow runs to completion. If it fails:
- Tests failing → fix on `main`, delete the tag, retag.
- `uv publish` failing with 403 → token misconfigured. Re-run Step 2.
- `uv publish` failing with "filename already exists" → version 0.1.0 already on PyPI. Bump to 0.1.1 and retag.

- [ ] **Step 6: Verify the package is live on PyPI**

Open https://pypi.org/project/jakpost-scraper/ in a browser. Expected: 0.1.0 visible with README rendered.

Also check from CLI: `curl -s https://pypi.org/pypi/jakpost-scraper/json | python -c "import sys, json; print(json.load(sys.stdin)['info']['version'])"`
Expected: `0.1.0`.

- [ ] **Step 7: Test the installer on a clean macOS shell**

In a new terminal (or a clean container/VM if you have one):

```bash
which uv 2>/dev/null || echo "uv not installed yet"
which jakpost-scrape 2>/dev/null || echo "jakpost-scrape not installed yet"

curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
```

Expected: installer runs end-to-end. Final output shows install path, config path, "Try: jakpost-scrape --help", and (if claude is missing) the claude nudge.

Then:
```bash
jakpost-scrape --help
```
Expected: help text including the new `--config`, `--data-dir`, `--reports-dir`, `--upgrade` flags.

```bash
jakpost-scrape --upgrade
```
Expected: prints the upgrade message, exits 0.

- [ ] **Step 8: Test the installer on a clean Windows PowerShell**

On a Windows machine (or VM):

```powershell
irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
jakpost-scrape --help
jakpost-scrape --upgrade
```

Expected: same end-to-end success as Step 7.

- [ ] **Step 9: Done**

The package is live, both installers work, and the release workflow is reusable for future versions. Future releases require only:

1. Bump `version` in `pyproject.toml`.
2. `git tag vX.Y.Z && git push --tags`.

---

## Self-Review

Checked the plan against the spec sections:

| Spec section | Implemented in |
|---|---|
| Goal — installable via one-liner, non-Python user friendly | Tasks 10, 11 |
| User experience — `curl | sh` and `irm | iex` commands | Tasks 10, 11, 13 |
| Approach — PyPI + `uv tool install` | Tasks 1, 10, 11, 12, 14 |
| Architecture — three artifacts (PyPI pkg, install.sh, install.ps1) | Tasks 1, 10, 11 |
| File path resolution — order CLI > env > cwd > default | Tasks 4, 7, 8 |
| Platform defaults table (macOS/Linux/Windows) | Task 3 (constants), Task 13 (README) |
| First-run behavior — write default config | Tasks 5, 8 |
| `claude` CLI dependency — installer checks, doesn't fail | Tasks 10, 11 |
| Upgrade UX — `--upgrade`/`--update` flag | Task 9 |
| `install.sh` 5-step flow | Task 10 |
| `install.ps1` 5-step flow | Task 11 |
| Idempotency — re-runnable | Tasks 10, 11 (`uv tool install --upgrade`) |
| Hosting — repo root, raw.githubusercontent.com | Tasks 10, 11, 13 |
| pyproject.toml: platformdirs, metadata, version 0.1.0 | Task 1 |
| config.py: paths default to None, resolved via paths.py | Tasks 6, 7 |
| cli.py: new flags | Tasks 8, 9 |
| LICENSE (MIT) | Task 2 |
| .github/workflows/release.yml | Task 12 |
| Release process — token, tag, workflow runs | Task 14 |
| README updates | Task 13 |
| state.json kept in path resolution (DECISIONS D-008) | Tasks 3 (`default_state_file`), 7 |

No gaps found. No placeholders (TBD/TODO) in any task. Type names checked: `Config`, `paths.PlatformDirs`, `resolve_config_path`, `resolve_data_dir`, `resolve_reports_dir`, `default_data_dir`, `default_reports_dir`, `default_state_file`, `default_config_path`, `ensure_default_config`, `DEFAULT_CONFIG_YAML` — all defined in Tasks 3–5 before they're called in Tasks 7–9.

One thing worth flagging at execution time: Task 6 deliberately leaves the test suite in a broken (red) state, which Task 7 then fixes. This is intentional and documented in Task 6 Step 5 — don't try to "fix" it within Task 6.
