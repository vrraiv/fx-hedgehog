from fx_treasury_risk import config
from fx_treasury_risk.data import registry


def test_keys_unique() -> None:
    keys = [s.key for s in registry.ALL_SERIES]
    assert len(keys) == len(set(keys))


def test_every_exposure_currency_has_three_fx_sources() -> None:
    for ccy in config.EXPOSURE_CCYS:
        assert registry.select(source="fred", category="fx", ccy=ccy), ccy
        # BoC quotes CAD per FCY, so CAD itself comes from the USD/CAD bridge series;
        # likewise the ECB quotes FCY per EUR, so EUR comes from the USD/EUR series.
        boc = registry.select(source="boc", category="fx", ccy="USD" if ccy == "CAD" else ccy)
        assert {s.vintage for s in boc} == {"current", "legacy"}, ccy
        ecb = registry.select(source="ecb", category="fx", ccy="USD" if ccy == "EUR" else ccy)
        assert len(ecb) == 1, ccy


def test_fx_specs_carry_a_quote_convention() -> None:
    for s in registry.select(category="fx"):
        assert s.quote is not None, s.key
    for s in registry.ALL_SERIES:
        if s.category != "fx":
            assert s.quote is None, s.key


def test_bridge_series_present() -> None:
    # the BoC and ECB conversions need USD/CAD and USD/EUR respectively
    assert registry.by_key("boc:FXUSDCAD").ccy == "USD"
    assert registry.by_key("boc:IEXE0101").vintage == "legacy"
    assert registry.by_key("ecb:D.USD.EUR.SP00.A").ccy == "USD"


def test_short_rate_coverage() -> None:
    # SGD has no public short-rate source (ADR-0006); every other currency has one
    covered = {s.ccy for s in registry.select(category="rate")} | {
        s.ccy for s in registry.select(category="policy_rate")
    }
    assert set(config.EXPOSURE_CCYS) - covered == {"SGD"}
    assert "USD" in covered
