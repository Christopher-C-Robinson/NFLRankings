"""v2 rating tests on a tiny synthetic play table (no network)."""

import pandas as pd
import pytest

from nflrankings.rating import adjust


def _plays():
    rows = []

    def add(off, dfn, epa, n=10):
        rows.extend({"posteam": off, "defteam": dfn, "epa": epa} for _ in range(n))

    # A and B both average 0.10 EPA/play on offense.
    # A faced the stout defense S (allows -0.1); B faced the soft defense W (+0.2).
    add("A", "S", 0.10)
    add("B", "W", 0.10)
    add("S", "W", 0.05)
    add("W", "S", -0.10)
    add("S", "A", 0.00)
    add("W", "B", 0.20)
    add("A", "W", 0.10, n=0)
    return pd.DataFrame(rows)


def test_stronger_schedule_gets_higher_adj_off():
    plays = _plays()
    res = adjust(plays)
    assert res.loc["A", "off_epa"] == pytest.approx(res.loc["B", "off_epa"])
    assert res.loc["A", "off_epa_adj"] > res.loc["B", "off_epa_adj"]


def test_deterministic():
    a = adjust(_plays())
    b = adjust(_plays().sample(frac=1.0, random_state=3).reset_index(drop=True))
    pd.testing.assert_frame_equal(a, b)
    assert list(a.sort_values("v2", ascending=False).index) == list(
        b.sort_values("v2", ascending=False).index
    )


def test_recentering_and_net():
    res = adjust(_plays())
    assert (res["off_epa_adj"] - res["off_epa"]).mean() == pytest.approx(0, abs=1e-9)
    assert (res["def_epa_adj"] - res["def_epa"]).mean() == pytest.approx(0, abs=1e-9)
    assert (res["v2"] - (res["off_epa_adj"] - res["def_epa_adj"])).abs().max() < 1e-12
