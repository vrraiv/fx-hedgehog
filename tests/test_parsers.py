"""Parsers are tested against real (trimmed) responses captured on 2026-11-05."""

import json

import pandas as pd
import pytest

from fx_treasury_risk.data import bis, boc, ecb, fred, statcan
from tests.conftest import FIXTURES


def test_boc_parse_observations() -> None:
    payload = json.loads((FIXTURES / "boc_observations.json").read_text(encoding="utf-8"))
    out = boc.parse_observations(payload)
    assert set(out) >= {"FXUSDCAD", "FXEURCAD", "FXJPYCAD"}
    usdcad = out["FXUSDCAD"]
    assert usdcad.index[0] == pd.Timestamp("2024-10-01")
    assert 1.3 < usdcad.iloc[0] < 1.4
    assert out["FXJPYCAD"].iloc[0] < 0.02  # CAD per 1 JPY


def test_boc_parse_skips_blank_values() -> None:
    payload = {
        "observations": [
            {"d": "2024-01-01", "X": {"v": ""}},
            {"d": "2024-01-02", "X": {"v": "1.5"}},
        ]
    }
    out = boc.parse_observations(payload)
    assert len(out["X"]) == 1 and out["X"].iloc[0] == 1.5


def test_fred_parse_csv() -> None:
    text = (FIXTURES / "fred_DEXUSEU.csv").read_text(encoding="utf-8")
    s = fred.parse_fredgraph_csv(text, "DEXUSEU")
    assert len(s) == 6
    assert s.loc["2024-10-01"] == pytest.approx(1.1067)


def test_fred_parse_csv_drops_dots_and_checks_column() -> None:
    text = "observation_date,DTB3\n2024-01-01,.\n2024-01-02,5.25\n"
    s = fred.parse_fredgraph_csv(text, "DTB3")
    assert list(s) == [5.25]
    with pytest.raises(ValueError):
        fred.parse_fredgraph_csv(text, "WRONG")


def test_fred_parse_api_json() -> None:
    payload = {
        "observations": [
            {"date": "2024-01-01", "value": "."},
            {"date": "2024-01-02", "value": "5.25"},
        ]
    }
    s = fred.parse_api_json(payload, "DTB3")
    assert list(s) == [5.25]


def test_ecb_parse_csvdata() -> None:
    text = (FIXTURES / "ecb_exr.csv").read_text(encoding="utf-8")
    out = ecb.parse_csvdata(text)
    assert set(out) == {
        "D.USD.EUR.SP00.A",
        "D.GBP.EUR.SP00.A",
        "D.JPY.EUR.SP00.A",
        "D.CAD.EUR.SP00.A",
    }
    assert out["D.CAD.EUR.SP00.A"].loc["2024-10-01"] == pytest.approx(1.4986)


def test_bis_parse_eer_and_cbpol() -> None:
    eer = bis.parse_csv((FIXTURES / "bis_eer.csv").read_text(encoding="utf-8"), "WS_EER")
    assert set(eer) >= {"D.N.B.US", "D.N.B.GB"}
    assert eer["D.N.B.GB"].loc["2024-10-01"] == pytest.approx(112.56)
    pol = bis.parse_csv((FIXTURES / "bis_cbpol.csv").read_text(encoding="utf-8"), "WS_CBPOL")
    assert "D.AU" in pol and "D.CA" in pol
    assert 4.0 < pol["D.AU"].iloc[0] < 5.0


def test_statcan_parse_vectors() -> None:
    payload = json.loads((FIXTURES / "statcan_vectors.json").read_text(encoding="utf-8"))
    out = statcan.parse_vectors(payload)
    assert set(out) == {"v1446859481", "v1446859483"}
    s = out["v1446859481"]
    assert s.index[0] == pd.Timestamp("2026-06-01")
    assert s.iloc[0] > 7e7  # thousands of CAD -> ~ CAD 78 bn
