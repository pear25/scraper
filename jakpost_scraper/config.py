"""Configuration: defaults, YAML file, and CLI overrides."""

import os
from dataclasses import dataclass, fields

import yaml

SUMMARY_MODES = ("per-article", "digest", "both")
PAYWALL_MODES = ("keep-teaser", "skip")


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class Config:
    sections: str | list[str] = "all"  # "all" or a list of section identifiers
    summary_mode: str = "both"
    model: str = "claude-haiku-4-5"
    paywall: str = "keep-teaser"
    request_delay: float = 1.0
    concurrency: int = 4
    lookback_buffer_minutes: int = 20
    seen_url_retention_days: int = 30
    http_timeout: int = 15
    http_retries: int = 3
    data_dir: str = "./data"
    reports_dir: str = "./reports"
    state_file: str = "./state.json"


def load_config(config_path: str | None, cli_overrides: dict) -> Config:
    """Build a Config from defaults, an optional YAML file, then CLI overrides."""
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
    validate_config(cfg)
    return cfg


def validate_config(cfg: Config) -> None:
    """Raise ConfigError if any field holds an invalid value."""
    if cfg.summary_mode not in SUMMARY_MODES:
        raise ConfigError(f"summary_mode must be one of {SUMMARY_MODES}")
    if cfg.paywall not in PAYWALL_MODES:
        raise ConfigError(f"paywall must be one of {PAYWALL_MODES}")
    for name in ("concurrency", "http_retries", "http_timeout",
                 "lookback_buffer_minutes", "seen_url_retention_days"):
        if getattr(cfg, name) < 1:
            raise ConfigError(f"{name} must be >= 1")
    if cfg.request_delay < 0:
        raise ConfigError("request_delay must be >= 0")
    if cfg.sections != "all" and not isinstance(cfg.sections, list):
        raise ConfigError('sections must be "all" or a list')
