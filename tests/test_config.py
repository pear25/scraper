import pytest

from jakpost_scraper.config import Config, ConfigError, load_config, validate_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {})
    assert cfg.summary_mode == "both"
    assert cfg.concurrency == 4
    assert cfg.sections == "all"


def test_yaml_overrides_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("summary_mode: digest\nconcurrency: 8\n")
    cfg = load_config(str(path), {})
    assert cfg.summary_mode == "digest"
    assert cfg.concurrency == 8


def test_cli_overrides_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("summary_mode: digest\n")
    cfg = load_config(str(path), {"summary_mode": "per-article"})
    assert cfg.summary_mode == "per-article"


def test_cli_none_values_ignored(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {"summary_mode": None})
    assert cfg.summary_mode == "both"


def test_unknown_yaml_key_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("bogus_key: 1\n")
    with pytest.raises(ConfigError, match="Unknown config key"):
        load_config(str(path), {})


def test_invalid_summary_mode_rejected():
    with pytest.raises(ConfigError, match="summary_mode"):
        validate_config(Config(summary_mode="nonsense"))


def test_negative_concurrency_rejected():
    with pytest.raises(ConfigError, match="concurrency"):
        validate_config(Config(concurrency=0))


def test_sections_list_accepted():
    validate_config(Config(sections=["business", "news/politics"]))


def test_sections_list_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("sections:\n  - business\n  - news/politics\n")
    cfg = load_config(str(path), {})
    assert cfg.sections == ["business", "news/politics"]


def test_auth_defaults_off(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {})
    assert cfg.auth_enabled is False
    assert cfg.auth_cookies_file == "./.auth/cookies.json"
    assert cfg.auth_login_url.endswith("/user/account/login")


def test_auth_keys_load_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("auth_enabled: true\n")
    cfg = load_config(str(path), {})
    assert cfg.auth_enabled is True


def test_path_defaults_are_none_before_resolution():
    """data_dir/reports_dir/state_file should default to None so load_config
    can distinguish unset from explicitly set."""
    cfg = Config()
    assert cfg.data_dir is None
    assert cfg.reports_dir is None
    assert cfg.state_file is None


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


def test_load_config_cli_override_wins_over_env(tmp_path, monkeypatch):
    """CLI explicit value must beat env var, which beats YAML, which beats default."""
    monkeypatch.setenv("JAKPOST_DATA_DIR", "/tmp/from_env")
    yaml = tmp_path / "config.yaml"
    yaml.write_text("")
    cfg = load_config(str(yaml), {"data_dir": "/tmp/from_cli"})
    assert cfg.data_dir == "/tmp/from_cli"


def test_state_file_follows_data_dir_override(tmp_path, monkeypatch):
    """When data_dir is redirected, state.json moves with it so dedup
    stays coherent across runs in the new location."""
    monkeypatch.delenv("JAKPOST_DATA_DIR", raising=False)
    yaml = tmp_path / "config.yaml"
    yaml.write_text("")
    cfg = load_config(str(yaml), {"data_dir": str(tmp_path / "custom")})
    assert cfg.data_dir == str(tmp_path / "custom")
    assert cfg.state_file == str(tmp_path / "custom" / "state.json")


def test_state_file_follows_data_dir_env_var(tmp_path, monkeypatch):
    """JAKPOST_DATA_DIR also pulls state.json along."""
    monkeypatch.setenv("JAKPOST_DATA_DIR", str(tmp_path / "envdata"))
    yaml = tmp_path / "config.yaml"
    yaml.write_text("")
    cfg = load_config(str(yaml), {})
    assert cfg.data_dir == str(tmp_path / "envdata")
    assert cfg.state_file == str(tmp_path / "envdata" / "state.json")
