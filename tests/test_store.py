import datetime as dt

from ris_mcp.store import (
    default_db_path, get_sync_state, open_db, set_sync_state, upsert_decision, upsert_law,
)


def test_default_db_path_under_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("RIS_MCP_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = default_db_path()
    assert p.parent.name == "ris-mcp"
    assert p.name == "ris.db"


def test_open_db_applies_schema(tmp_db):
    cur = tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    assert {"decisions", "laws", "sync_state"}.issubset(tables)


def test_upsert_decision_round_trips_and_indexes_fts(tmp_db):
    upsert_decision(tmp_db, {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G123/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG", "schlagworte": "Gleichheit",
        "rechtssatz": None, "text": "Die Beschwerde wird abgewiesen.",
        "text_html": "<p>Die Beschwerde wird abgewiesen.</p>",
        "source_url": "https://example.test/x",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00",
        "raw_json": "{}",
    })
    rows = tmp_db.execute(
        "SELECT rowid FROM decisions_fts WHERE decisions_fts MATCH 'Beschwerde'"
    ).fetchall()
    assert rows


def test_upsert_decision_updates_existing(tmp_db):
    base = {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": None,
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "old", "text_html": None, "source_url": None,
        "fetched_at": "2024-06-01T00:00:00", "aenderungsdatum": "2024-06-01T00:00:00",
        "raw_json": "{}",
    }
    upsert_decision(tmp_db, base)
    upsert_decision(tmp_db, {**base, "text": "new"})
    rows = tmp_db.execute("SELECT text FROM decisions WHERE id='Vfgh:abc'").fetchall()
    assert [tuple(r) for r in rows] == [("new",)]


def test_upsert_law_round_trips(tmp_db):
    upsert_law(tmp_db, {
        "id": "10001622:879", "gesetzesnummer": "10001622", "kurztitel": "ABGB",
        "langtitel": "Allgemeines bürgerliches Gesetzbuch", "paragraf": "879",
        "absatz": None, "ueberschrift": "Sittenwidrige Geschäfte",
        "text": "Ein Vertrag, der gegen ein gesetzliches Verbot...",
        "fassung_vom": "2024-01-01", "source_url": None,
        "fetched_at": "2024-06-01T00:00:00", "raw_json": "{}",
    })
    rows = tmp_db.execute("SELECT rowid FROM laws_fts WHERE laws_fts MATCH 'Sittenwidrig*'").fetchall()
    assert rows


def test_sync_state_round_trip(tmp_db):
    assert get_sync_state(tmp_db, "Vfgh") is None
    set_sync_state(tmp_db, "Vfgh", watermark="2024-06-01T00:00:00", delta=True, total=42)
    s = get_sync_state(tmp_db, "Vfgh")
    assert s["watermark_aenderungsdatum"] == "2024-06-01T00:00:00"
    assert s["total_docs"] == 42
