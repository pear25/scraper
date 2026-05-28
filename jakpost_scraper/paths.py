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
