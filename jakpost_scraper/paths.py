"""Platform-default paths for installed CLI usage.

Resolution order (highest priority first) is implemented in `resolve_*`
functions: CLI flag > env var > cwd (if config.yaml exists) > platform
default. The constants in this module describe only the platform-default
layer.
"""

import os
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


ENV_CONFIG = "JAKPOST_CONFIG"
ENV_DATA_DIR = "JAKPOST_DATA_DIR"
ENV_REPORTS_DIR = "JAKPOST_REPORTS_DIR"


def resolve_config_path(explicit_path: str | None) -> Path:
    """Resolve the config.yaml path.

    Order: explicit CLI flag > JAKPOST_CONFIG env > cwd/config.yaml if it
    exists > platform default. Returns the chosen Path even if it doesn't
    exist on disk (load_config decides what to do with that).
    """
    if explicit_path is not None:
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

    There is no cwd fallback for data — only config.yaml triggers cwd-mode
    (so a project-local config.yaml drags state/data along with it via
    load_config's resolution; see resolve_config_path)."""
    if explicit_path is not None:
        return Path(explicit_path)
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env)
    return default_data_dir()


def resolve_reports_dir(explicit_path: str | None) -> Path:
    """Resolve the reports directory. Order: explicit > env > platform default."""
    if explicit_path is not None:
        return Path(explicit_path)
    env = os.environ.get(ENV_REPORTS_DIR)
    if env:
        return Path(env)
    return default_reports_dir()


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


def ensure_default_config(path: Path) -> bool:
    """Write the shipped default config to `path` if it doesn't exist.

    Returns True if a file was written, False if one already existed.
    Creates parent directories as needed."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_YAML)
    return True
