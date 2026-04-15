from ris_mcp.applikation import REGISTRY, ApplikationConfig, get_applikation


def test_registry_includes_apex_courts():
    codes = {a.code for a in REGISTRY}
    assert {"Justiz", "Vfgh", "Vwgh", "Bvwg"}.issubset(codes)


def test_registry_includes_lvwg_per_land():
    codes = {a.code for a in REGISTRY}
    # LVwG is split per Bundesland in RIS API; expect 9
    lvwg = {c for c in codes if c.startswith("Lvwg")}
    assert len(lvwg) == 9


def test_each_applikation_has_normalised_court():
    for a in REGISTRY:
        assert isinstance(a, ApplikationConfig)
        assert a.court  # non-empty normalised label


def test_get_applikation_lookup():
    cfg = get_applikation("Vfgh")
    assert cfg.court == "VfGH"


def test_get_applikation_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_applikation("DoesNotExist")


def test_registry_codes_are_unique():
    codes = [a.code for a in REGISTRY]
    assert len(codes) == len(set(codes))
