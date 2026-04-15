import datetime as dt

import pytest

from ris_mcp.store import upsert_decision
from ris_mcp.tools.get_decision import get_decision


def _seed(conn):
    upsert_decision(conn, {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG | Art. 8 B-VG", "schlagworte": "Gleichheit | Sprache",
        "rechtssatz": None, "text": "Volltext", "text_html": "<p>Volltext</p>",
        "source_url": "https://x", "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00", "raw_json": "{}",
    })


def test_get_by_id(tmp_db):
    _seed(tmp_db)
    out = get_decision(tmp_db, id="Vfgh:abc")
    assert out["geschaeftszahl"] == "G1/24"
    assert out["norm"] == ["Art. 7 B-VG", "Art. 8 B-VG"]
    assert out["schlagworte"] == ["Gleichheit", "Sprache"]
    assert out["text"] == "Volltext"


def test_get_by_geschaeftszahl(tmp_db):
    _seed(tmp_db)
    out = get_decision(tmp_db, geschaeftszahl="G1/24")
    assert out["id"] == "Vfgh:abc"


def test_neither_arg_raises(tmp_db):
    with pytest.raises(ValueError):
        get_decision(tmp_db)


def test_not_found_returns_none(tmp_db):
    assert get_decision(tmp_db, id="missing") is None
