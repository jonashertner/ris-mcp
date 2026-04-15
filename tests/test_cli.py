from click.testing import CliRunner

from ris_mcp.cli import ingest_main, mcp_main


def test_ingest_help():
    r = CliRunner().invoke(ingest_main, ["--help"])
    assert r.exit_code == 0
    assert "--full" in r.output and "--delta" in r.output


def test_mcp_help():
    r = CliRunner().invoke(mcp_main, ["--help"])
    assert r.exit_code == 0
