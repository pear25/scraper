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
