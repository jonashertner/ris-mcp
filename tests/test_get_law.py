from ris_mcp.store import upsert_law
from ris_mcp.tools.get_law import get_law, normalise_paragraf


def _seed(conn):
    upsert_law(conn, {
        "id": "10001622:879", "gesetzesnummer": "10001622", "kurztitel": "ABGB",
        "langtitel": "Allgemeines bürgerliches Gesetzbuch", "paragraf": "879",
        "absatz": None, "ueberschrift": "Sittenwidrige Geschäfte",
        "text": "Ein Vertrag, der gegen ein gesetzliches Verbot verstößt, ist nichtig.",
        "fassung_vom": "2024-01-01", "source_url": "https://x",
        "fetched_at": "2024-06-01T00:00:00", "raw_json": "{}",
    })


def test_get_law_by_kurztitel(tmp_db):
    _seed(tmp_db)
    out = get_law(tmp_db, kurztitel="ABGB", paragraf="879")
    assert out is not None
    assert "nichtig" in out["text"]


def test_get_law_handles_paragraf_prefix(tmp_db):
    _seed(tmp_db)
    assert get_law(tmp_db, kurztitel="ABGB", paragraf="§ 879") is not None
    assert get_law(tmp_db, kurztitel="abgb", paragraf="879") is not None


def test_normalise_paragraf():
    assert normalise_paragraf("§ 879") == "879"
    assert normalise_paragraf("Art. 7") == "7"
    assert normalise_paragraf("879") == "879"
    assert normalise_paragraf("§879") == "879"
