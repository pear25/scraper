from jakpost_scraper.cli import build_parser, cli_overrides


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.since is None
    assert args.dry_run is False
    assert args.no_summary is False
    assert args.summary_mode is None
    assert args.console_output is None
    assert args.limit is None
    assert args.sections is None


def test_parser_flags():
    args = build_parser().parse_args(
        ["--since", "24h", "--dry-run", "--no-summary",
         "--summary-mode", "digest", "--console-output", "article-text",
         "--limit", "5", "--sections", "business"])
    assert args.since == "24h"
    assert args.dry_run is True
    assert args.no_summary is True
    assert args.summary_mode == "digest"
    assert args.console_output == "article-text"
    assert args.limit == 5
    assert args.sections == "business"


def test_console_output_flag_parses():
    args = build_parser().parse_args(["--console-output", "article-text"])
    assert args.console_output == "article-text"


def test_cli_overrides_extracts_config_keys():
    args = build_parser().parse_args(
        ["--summary-mode", "both", "--sections", "business, news/politics"])
    overrides = cli_overrides(args)
    assert overrides["summary_mode"] == "both"
    assert overrides["sections"] == ["business", "news/politics"]


def test_cli_overrides_empty_when_no_flags():
    args = build_parser().parse_args([])
    assert cli_overrides(args) == {}


def test_auth_flags_parse():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args(["--auth", "--reauth"])
    assert args.auth is True
    assert args.reauth is True


def test_no_auth_flag_parses():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args(["--no-auth"])
    assert args.auth is False


def test_auth_defaults_to_none_when_unset():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args([])
    assert args.auth is None
    assert args.reauth is False


def _article(is_premium, is_truncated):
    from datetime import datetime, timezone
    from jakpost_scraper.models import Article
    when = datetime(2026, 5, 20, tzinfo=timezone.utc)
    return Article(url="u", title="t", section="s", published_at=when,
                   authors=[], body="b", is_paywalled=is_truncated,
                   is_premium=is_premium, is_truncated=is_truncated,
                   lead_image_url=None, scraped_at=when)


def test_session_looks_dead_when_majority_premium_truncated():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(True, True), _article(True, True), _article(True, False)]
    assert _session_looks_dead(arts) is True


def test_session_ok_when_minority_truncated():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(True, False), _article(True, False), _article(True, True)]
    assert _session_looks_dead(arts) is False


def test_session_ok_when_no_premium_articles():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(False, False), _article(False, False)]
    assert _session_looks_dead(arts) is False


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
