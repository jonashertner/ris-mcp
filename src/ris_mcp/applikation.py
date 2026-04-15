"""Registry of Austrian RIS Judikatur 'Applikationen' (data sources).

The exact list and code spelling is canonical to the RIS Web Service v2.6 API at
https://data.bka.gv.at/ris/api/v2.6/Judikatur. This file is the single source of
truth for which sources we ingest.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplikationConfig:
    code: str          # exact RIS Applikation parameter value
    court: str         # normalised court label used in our schema
    description: str   # human-readable description (en)


REGISTRY: tuple[ApplikationConfig, ...] = (
    ApplikationConfig("Justiz", "Justiz", "Ordinary courts (OGH/OLG/LG/BG) — civil & criminal"),
    ApplikationConfig("Vfgh", "VfGH", "Constitutional Court"),
    ApplikationConfig("Vwgh", "VwGH", "Supreme Administrative Court"),
    ApplikationConfig("Bvwg", "BVwG", "Federal Administrative Court"),
    ApplikationConfig("LvwgBgld", "LVwG-Bgld", "Burgenland LVwG"),
    ApplikationConfig("LvwgKtn", "LVwG-Ktn", "Kärnten LVwG"),
    ApplikationConfig("LvwgNoe", "LVwG-NÖ", "Niederösterreich LVwG"),
    ApplikationConfig("LvwgOoe", "LVwG-OÖ", "Oberösterreich LVwG"),
    ApplikationConfig("LvwgSbg", "LVwG-Sbg", "Salzburg LVwG"),
    ApplikationConfig("LvwgStmk", "LVwG-Stmk", "Steiermark LVwG"),
    ApplikationConfig("LvwgTir", "LVwG-Tir", "Tirol LVwG"),
    ApplikationConfig("LvwgVbg", "LVwG-Vbg", "Vorarlberg LVwG"),
    ApplikationConfig("LvwgWien", "LVwG-Wien", "Wien LVwG"),
    ApplikationConfig("Dsk", "DSK", "Datenschutzkommission (historical)"),
    ApplikationConfig("Dsb", "DSB", "Datenschutzbehörde"),
    ApplikationConfig("Gbk", "GBK", "Gleichbehandlungskommission"),
    ApplikationConfig("Pvak", "PVAK", "Personalvertretungs-Aufsichtskommission"),
)

# NOTE: real Applikation enum will be confirmed during Task 3 first live smoke
# test. If RIS reports a different code spelling for any LVwG, fix here and
# re-run tests.

_BY_CODE = {a.code: a for a in REGISTRY}


def get_applikation(code: str) -> ApplikationConfig:
    return _BY_CODE[code]
