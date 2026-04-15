# tests/test_coverage.py
import datetime as dt
import json

from ris_mcp.coverage import generate_coverage
from ris_mcp.store import upsert_decision, upsert_law


def _seed(conn):
    now = dt.datetime.utcnow().isoformat()
    upsert_decision(conn, {
        "id": "Vfgh:1", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "x", "text_html": None, "source_url": None,
        "fetched_at": now, "aenderungsdatum": "2024-06-02T10:00:00",
        "raw_json": "{}",
    })
    upsert_decision(conn, {
        "id": "Vwgh:1", "applikation": "Vwgh", "court": "VwGH",
        "geschaeftszahl": "Ra1/24", "entscheidungsdatum": "2024-05-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "y", "text_html": None, "source_url": None,
        "fetched_at": now, "aenderungsdatum": "2024-05-02T10:00:00",
        "raw_json": "{}",
    })
    upsert_law(conn, {
        "id": "10001622:879", "gesetzesnummer": "10001622",
        "kurztitel": "ABGB", "langtitel": "ABGB",
        "paragraf": "879", "absatz": None, "ueberschrift": None,
        "text": "nichtig.", "fassung_vom": "2024-01-01", "source_url": None,
        "fetched_at": now, "raw_json": "{}",
    })


def test_coverage_counts(tmp_db):
    _seed(tmp_db)
    out = generate_coverage(tmp_db)
    assert out["total_decisions"] == 2
    assert out["total_laws"] == 1
    assert out["decisions_by_court"] == {"VfGH": 1, "VwGH": 1}
    assert out["corpus_span"]["earliest"] == "2024-05-01"
    assert out["corpus_span"]["latest"] == "2024-06-01"
    assert out["last_aenderungsdatum"] == "2024-06-02T10:00:00"
    assert out["schema_version"] == 1
    assert "generated_at" in out


def test_coverage_empty_db(tmp_db):
    out = generate_coverage(tmp_db)
    assert out["total_decisions"] == 0
    assert out["total_laws"] == 0
    assert out["decisions_by_court"] == {}
    assert out["corpus_span"]["earliest"] is None
    assert out["corpus_span"]["latest"] is None
    assert out["last_aenderungsdatum"] is None


def test_coverage_output_is_json_serialisable(tmp_db):
    _seed(tmp_db)
    out = generate_coverage(tmp_db)
    json.dumps(out)  # raises if not serialisable
