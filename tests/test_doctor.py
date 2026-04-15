from pathlib import Path

from ris_mcp.doctor import (
    Check,
    check_db_contents,
    check_db_file,
    check_python,
    check_uvx,
    format_report,
    run_diagnostics,
)
from ris_mcp.store import upsert_decision


def test_check_python_ok():
    c = check_python()
    assert c.status == "ok"


def test_check_uvx_found(monkeypatch):
    monkeypatch.setattr("ris_mcp.doctor.shutil.which",
                       lambda name: "/fake/bin/uvx" if name == "uvx" else None)
    c = check_uvx()
    assert c.status == "ok"
    assert "/fake/bin/uvx" in c.detail


def test_check_uvx_missing(monkeypatch):
    monkeypatch.setattr("ris_mcp.doctor.shutil.which", lambda n: None)
    c = check_uvx()
    assert c.status == "fail"
    assert "install uv" in c.hint.lower()


def test_check_db_file_missing(tmp_path):
    c = check_db_file(tmp_path / "nope.db")
    assert c.status == "fail"
    assert "import-from-hf" in c.hint


def test_check_db_file_tiny(tmp_path):
    p = tmp_path / "empty.db"
    p.write_bytes(b"")
    c = check_db_file(p)
    assert c.status == "warn"


def test_check_db_file_ok(tmp_path):
    p = tmp_path / "big.db"
    p.write_bytes(b"x" * 20000)
    c = check_db_file(p)
    assert c.status == "ok"


def test_check_db_contents_empty_db(tmp_db, tmp_path):
    db_path = Path(tmp_db.execute("PRAGMA database_list").fetchone()[2])
    tmp_db.close()
    c = check_db_contents(db_path)
    assert c.status == "warn"


def test_check_db_contents_populated(tmp_db, tmp_path):
    upsert_decision(tmp_db, {
        "id": "X:1", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "x", "text_html": None, "source_url": None,
        "fetched_at": "2024-06-01T00:00:00",
        "aenderungsdatum": "2024-06-02T10:00:00", "raw_json": "{}",
    })
    db_path = Path(tmp_db.execute("PRAGMA database_list").fetchone()[2])
    tmp_db.close()
    c = check_db_contents(db_path)
    assert c.status == "ok"
    assert "1 decisions" in c.detail or "1," in c.detail


def test_run_diagnostics_returns_list():
    checks = run_diagnostics()
    assert isinstance(checks, list)
    assert all(isinstance(c, Check) for c in checks)
    assert len(checks) >= 4


def test_format_report_emits_status_line():
    checks = [
        Check("a", "ok", "fine"),
        Check("b", "ok", "also fine"),
    ]
    out = format_report(checks)
    assert "all good" in out.lower()


def test_format_report_flags_failures():
    checks = [
        Check("a", "ok", "fine"),
        Check("b", "fail", "broken", hint="do X"),
    ]
    out = format_report(checks)
    assert "attention" in out.lower()
    assert "do X" in out
