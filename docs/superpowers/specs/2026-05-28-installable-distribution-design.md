# Installable Distribution Design

**Date:** 2026-05-28
**Status:** Draft — awaiting user review

## Goal

Make `jakpost-scraper` installable on Mac, Linux, and Windows via a single
shell one-liner, without requiring users to clone the repo, install Python,
or know what `pip` is. After install, the `jakpost-scrape` command is on the
user's PATH and runs from any working directory.

Target audience: **non-Python users**. The installer must handle Python
itself, not just the package.

## User experience

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
```

After install, `jakpost-scrape --help` works from anywhere.

## Approach: PyPI + thin installer scripts using `uv`

Publish the existing Python package to PyPI. The installer scripts:
1. Install [`uv`](https://github.com/astral-sh/uv) (a standalone tool
   installer, single binary, no Python prereq) if missing.
2. Run `uv tool install jakpost-scraper`. `uv` downloads a compatible
   Python 3.11+ if the user has none, in an isolated environment.
3. Print post-install guidance including the optional `claude` CLI nudge.

Alternatives considered: standalone binaries via PyInstaller (rejected — big
build matrix, antivirus issues, `claude-agent-sdk` may not bundle cleanly);
Homebrew tap + Scoop bucket (rejected as primary — not a one-liner, but may
be added later).

## Architecture

Three artifacts:

1. **PyPI package `jakpost-scraper`** — the existing package, published
   to PyPI. Entry point `jakpost-scrape` already declared in
   [pyproject.toml](../../../pyproject.toml).
2. **`install.sh`** — POSIX shell installer at repo root, served via
   `raw.githubusercontent.com`.
3. **`install.ps1`** — PowerShell installer at repo root, served the
   same way.

## File path resolution

The installed CLI needs platform-appropriate default paths since
`./config.yaml`, `./state.json`, `./data/`, and `./reports/` won't work for
a global install.

**Resolution order (highest priority first):**

1. CLI flag (e.g. `--config`, `--data-dir`, `--reports-dir`).
2. Environment variable (`JAKPOST_CONFIG`, `JAKPOST_DATA_DIR`,
   `JAKPOST_REPORTS_DIR`).
3. Current working directory — *only if `config.yaml` exists there*.
   Preserves today's "run from repo" behavior for developers.
4. Platform default via [`platformdirs`](https://pypi.org/project/platformdirs/).

**Platform defaults:**

| OS      | Config                                                       | State + data                                     | Reports                                  |
|---------|--------------------------------------------------------------|--------------------------------------------------|------------------------------------------|
| macOS   | `~/Library/Application Support/jakpost-scraper/config.yaml`  | `~/Library/Application Support/jakpost-scraper/` | `~/Documents/jakpost-reports/`           |
| Linux   | `~/.config/jakpost-scraper/config.yaml`                      | `~/.local/share/jakpost-scraper/`                | `~/Documents/jakpost-reports/`           |
| Windows | `%APPDATA%\jakpost-scraper\config.yaml`                      | `%APPDATA%\jakpost-scraper\`                     | `%USERPROFILE%\Documents\jakpost-reports\` |

**First-run behavior:** if no config is found at any priority level, the
CLI auto-creates the platform-default config directory, writes a default
`config.yaml` (the current shipped one), and prints where it put things.
State and data directories are created on demand.

## `claude` CLI dependency

The scraper's summarization step depends on the `claude` CLI being installed
and authenticated. The installer **does not bundle or install `claude`** —
we don't own that install/auth flow.

**Installer behavior:** after `uv tool install` succeeds, the installer
checks for `claude` on PATH. If missing, it prints a clear notice with the
install link and explains that `--no-summary` works without it. The install
**does not fail**.

**CLI behavior:** unchanged. The summarizer already has a preflight check
that fails clearly if `claude` is missing — see
[summarizer.py](../../../jakpost_scraper/summarizer.py).

## Upgrade UX

Add `--upgrade` (alias `--update`) as a top-level flag on `jakpost-scrape`.
When passed, the CLI prints the upgrade command and exits 0 without running
a scrape:

```
To upgrade jakpost-scraper, run:

  uv tool upgrade jakpost-scraper

Or re-run the installer:
  macOS/Linux:  curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
  Windows:      irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
```

The CLI does not invoke `uv` itself — running a package manager from the
package it manages is fragile (permissions, mid-upgrade restarts).

## Installer script details

### `install.sh` (POSIX)

`set -eu` at top. Steps:

1. **Preflight** — check `curl` is on PATH; abort with a clear message if not.
2. **Install `uv`** — if `uv` is not on PATH, run uv's official installer:
   `curl -LsSf https://astral.sh/uv/install.sh | sh`. Re-source PATH so the
   next step finds `uv`.
3. **Install the tool** — `uv tool install jakpost-scraper`.
4. **Check `claude` CLI** — `command -v claude >/dev/null` test. Print
   notice if missing; do not fail.
5. **Final message** — show install path, default config location for the
   user's OS, `jakpost-scrape --help` hint, and (if `claude` missing) the
   summary-setup steps.

### `install.ps1` (PowerShell)

`$ErrorActionPreference = 'Stop'` at top. Same shape:

1. Verify PowerShell 5.1+ (for `Invoke-RestMethod`).
2. `irm https://astral.sh/uv/install.ps1 | iex` if uv is missing.
3. `uv tool install jakpost-scraper`.
4. Check for `claude` via `Get-Command claude -ErrorAction SilentlyContinue`.
5. Print results.

### Idempotency

Both scripts are safe to re-run. `uv tool install` upgrades or no-ops if
already installed.

### Hosting

Scripts live at the repo root, served via `raw.githubusercontent.com`. No
separate CDN. Users can read the script before piping to `sh`.

## Code changes

### `pyproject.toml`

- Add `platformdirs` to `dependencies`.
- Tighten metadata: `license`, `readme = "README.md"`, `authors`, `urls`
  (Homepage, Repository, Issues), `classifiers` (Python versions, OS,
  license).
- Bump version for the release that includes these changes.

### [jakpost_scraper/config.py](../../../jakpost_scraper/config.py)

- Default `data_dir`, `reports_dir`, `state_file` to `None`. `load_config`
  fills in platform defaults when nothing is configured.
- Add the resolution order described above. Implement using
  `platformdirs.PlatformDirs("jakpost-scraper")`.
- First-run helper: when no config file is found anywhere, create the
  platform-default config dir, write a default `config.yaml`, and log
  where it went.

### [jakpost_scraper/cli.py](../../../jakpost_scraper/cli.py)

- Add `--config`, `--data-dir`, `--reports-dir` flags.
- Add `--upgrade` / `--update` flag that prints the upgrade command and
  exits 0.
- Honor env vars `JAKPOST_CONFIG`, `JAKPOST_DATA_DIR`, `JAKPOST_REPORTS_DIR`.

### New files

- `install.sh` — POSIX installer.
- `install.ps1` — PowerShell installer.
- `LICENSE` — pick a license (MIT recommended) and reference in
  `pyproject.toml`.
- `.github/workflows/release.yml` — GitHub Actions release workflow.

## Release process

**One-time setup:**

- Create PyPI account, generate an API token scoped to the
  `jakpost-scraper` project.
- Store token as a GitHub Actions secret `PYPI_API_TOKEN`.

**Release flow:**

1. Bump `version` in `pyproject.toml`.
2. Tag the commit: `git tag v0.2.0 && git push --tags`.
3. GitHub Actions workflow triggered on tags matching `v*`:
   - Installs `uv` and Python.
   - Runs the test suite.
   - Builds sdist + wheel (`uv build`).
   - Publishes to PyPI (`uv publish` with the token).
   - Creates a GitHub Release with the built artifacts attached.
4. Manually verify the install flow on a clean macOS shell and a clean
   Windows PowerShell. CI can't fully simulate `curl | sh`.

## Documentation updates

### `README.md`

- Restructure: install one-liner is the first thing after the description.
- Move "develop from source" instructions below.
- Add "Configuration file locations" subsection with the platform-default
  paths table.
- Document `--config`, `--data-dir`, `--reports-dir`, `--upgrade` flags.

### `INSTALL.md` (only if README gets too long)

Detailed install + troubleshooting: uv not on PATH, `claude` CLI setup,
where to find config, how to uninstall via `uv tool uninstall
jakpost-scraper`.

## Out of scope

- Homebrew tap / Scoop bucket — may be added later as additional channels.
- Standalone single-file binaries (PyInstaller, etc.).
- Bundling or auto-installing the `claude` CLI.
- Auto-update on launch.
- Migration tooling for existing source-install users (they keep working
  via the cwd-fallback path).

## Open questions

None — all resolved during brainstorming.
