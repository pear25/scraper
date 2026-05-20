from jakpost_scraper.cli import build_parser, cli_overrides


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.since is None
    assert args.dry_run is False
    assert args.no_summary is False
    assert args.summary_mode is None
    assert args.limit is None
    assert args.sections is None


def test_parser_flags():
    args = build_parser().parse_args(
        ["--since", "24h", "--dry-run", "--no-summary",
         "--summary-mode", "digest", "--limit", "5", "--sections", "business"])
    assert args.since == "24h"
    assert args.dry_run is True
    assert args.no_summary is True
    assert args.summary_mode == "digest"
    assert args.limit == 5
    assert args.sections == "business"


def test_cli_overrides_extracts_config_keys():
    args = build_parser().parse_args(
        ["--summary-mode", "both", "--sections", "business, news/politics"])
    overrides = cli_overrides(args)
    assert overrides["summary_mode"] == "both"
    assert overrides["sections"] == ["business", "news/politics"]


def test_cli_overrides_empty_when_no_flags():
    args = build_parser().parse_args([])
    assert cli_overrides(args) == {}
