import datetime as dt

from ris_mcp.store import upsert_decision
from ris_mcp.tools.search_decisions import search_decisions


def _seed(conn):
    upsert_decision(conn, {
        "id": "Vfgh:1", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG", "schlagworte": "Gleichheit",
        "rechtssatz": None, "text": "Die Beschwerde betreffend Gleichheit wird abgewiesen.",
        "text_html": None, "source_url": "https://x/1",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00", "raw_json": "{}",
    })
    upsert_decision(conn, {
        "id": "Vwgh:1", "applikation": "Vwgh", "court": "VwGH",
        "geschaeftszahl": "Ra2024/01/0001", "entscheidungsdatum": "2024-05-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "§ 879 ABGB", "schlagworte": "Sittenwidrigkeit",
        "rechtssatz": None, "text": "Sittenwidrigkeit eines Vertrags...",
        "text_html": None, "source_url": "https://x/2",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-05-02T10:00:00", "raw_json": "{}",
    })


def test_search_returns_fts_match(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Sittenwidrigkeit")
    assert len(out) == 1
    assert out[0]["geschaeftszahl"] == "Ra2024/01/0001"
    assert out[0]["court"] == "VwGH"


def test_search_filters_by_court(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Beschwerde OR Vertrag", court="VfGH")
    assert all(r["court"] == "VfGH" for r in out)


def test_search_respects_date_range(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Beschwerde OR Vertrag", date_from="2024-05-15", date_to="2024-12-31")
    assert {r["geschaeftszahl"] for r in out} == {"G1/24"}


def test_search_returns_snippet(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Gleichheit")
    assert "Gleichheit" in out[0]["snippet"]
