# tests/test_cli.py
from click.testing import CliRunner

from ris_mcp.cli import ingest_main, mcp_main


def test_ingest_help_shows_flags_and_subcommands():
    r = CliRunner().invoke(ingest_main, ["--help"])
    assert r.exit_code == 0
    assert "--full" in r.output and "--delta" in r.output
    assert "coverage" in r.output


def test_ingest_requires_flag_or_subcommand():
    r = CliRunner().invoke(ingest_main, [])
    assert r.exit_code != 0
    assert "specify --full, --delta, or a subcommand" in r.output


def test_coverage_subcommand_help():
    r = CliRunner().invoke(ingest_main, ["coverage", "--help"])
    assert r.exit_code == 0
    assert "--out" in r.output


def test_mcp_help():
    r = CliRunner().invoke(mcp_main, ["--help"])
    assert r.exit_code == 0
