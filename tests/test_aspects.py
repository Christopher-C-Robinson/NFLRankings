"""Dynamic aspect weights. No network and no full play-by-play file."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nflrankings.aspects import (
    CHECK_SEASONS,
    adjust_components,
    apply_fit,
    beats_both,
    closing_line_scores,
    evaluate,
    expected_starter,
    fit_season,
    haversine_miles,
    report_on_or_before,
    season_weight,
    unit_matchup,
)
from nflrankings.rating import adjust


def _games(seasons, slope, rng, n=70):
    rows = []
    for season in seasons:
        for _ in range(n):
            gap = float(rng.normal())
            base = 1.0
            rows.append({
                "season": season,
                "week": 1 + (len(rows) % 18),
                "margin": base + slope * gap,
                "base": base,
                "pass_matchup": gap,
                "spread_line": -3.0 if gap > 0 else 3.0,
            })
    return pd.DataFrame(rows)


def test_matchup_negates_when_the_clubs_swap():
    edge = unit_matchup(0.4, -0.1, 0.1, 0.2)
    assert edge == pytest.approx(-unit_matchup(0.1, 0.2, 0.4, -0.1))


def test_expected_starter_skips_unavailable_quarterbacks():
    assert expected_starter(["aaa", "bbb"], {"aaa"}) == "bbb"
    assert expected_starter(["aaa"], {"aaa"}) is None
    assert expected_starter(["", "bbb"], set()) == "bbb"


def test_report_date_after_the_game_is_not_pregame():
    game = pd.Timestamp("2024-09-08").date()
    assert report_on_or_before(None, game)
    assert report_on_or_before(pd.Timestamp("2024-09-06").date(), game)
    assert not report_on_or_before(pd.Timestamp("2024-09-09").date(), game)
    assert report_on_or_before(game, float("nan"))


def test_haversine_new_york_to_miami_is_about_a_thousand_miles():
    miles = haversine_miles(40.7128, -74.0060, 25.7617, -80.1918)
    assert 1000 < miles < 1200


def test_adjust_components_matches_the_published_adjuster_when_both_sides_exist():
    rows = []
    clubs = ("AAA", "BBB", "CCC", "DDD")
    play_id = 0
    for home, away, epa in (
        ("AAA", "BBB", 0.4), ("BBB", "AAA", -0.2), ("CCC", "DDD", 0.1), ("DDD", "CCC", 0.3),
        ("AAA", "CCC", -0.1), ("CCC", "AAA", 0.2), ("BBB", "DDD", 0.5), ("DDD", "BBB", -0.4),
        ("AAA", "DDD", 0.0), ("BBB", "CCC", 0.15),
    ):
        play_id += 1
        rows.append({"posteam": home, "defteam": away, "epa": epa})
        rows.append({"posteam": away, "defteam": home, "epa": -epa / 2})
    frame = pd.DataFrame(rows)
    got = adjust_components(frame)
    exp = adjust(frame)
    for team in exp.index:
        assert got.loc[team, "off_adj"] == pytest.approx(exp.loc[team, "off_epa_adj"], abs=1e-9)
        assert got.loc[team, "def_adj"] == pytest.approx(exp.loc[team, "def_epa_adj"], abs=1e-9)


def test_adjust_components_does_not_invent_a_zero_for_a_missing_side():
    frame = pd.DataFrame([
        {"posteam": "AAA", "defteam": "BBB", "epa": 0.5},
        {"posteam": "BBB", "defteam": "AAA", "epa": -0.2},
        {"posteam": "BBB", "defteam": "CCC", "epa": 0.1},
        {"posteam": "AAA", "defteam": "CCC", "epa": 0.2},
    ])
    got = adjust_components(frame)
    assert pd.isna(got.loc["CCC", "off_adj"])
    assert got.loc["CCC", "def_n"] > 0
    assert got.loc["AAA", "off_n"] > 0


def test_recent_season_weighs_more_when_the_half_life_is_short():
    rows = []
    for season, slope in ((2019, 0.0), (2020, 8.0)):
        for gap in np.linspace(-2, 2, 40):
            rows.append({"season": season, "week": 1, "base": 0.0, "margin": slope * float(gap), "x": float(gap)})
    frame = pd.DataFrame(rows)
    short = fit_season(frame, ["x"], 2021, scale=7.0, window=4, half_life=0.5, lambdas=(0.01,))
    flat = fit_season(frame, ["x"], 2021, scale=7.0, window=4, half_life=None, lambdas=(0.01,))
    assert short.train_seasons == (2019, 2020)
    assert short.beta[0] > flat.beta[0]
    assert season_weight(2019, 2020, 2.0) == pytest.approx(0.5 ** 0.5)


def test_target_season_cannot_change_its_own_weights():
    rng = np.random.default_rng(2)
    frame = _games(range(2018, 2026), slope=5.0, rng=rng)
    fit = fit_season(frame, ["pass_matchup"], 2024, scale=7.0, window=4, half_life=2.0, lambdas=(0.01,))
    corrupt = frame.copy()
    corrupt.loc[corrupt["season"] >= 2024, "margin"] = 0.0
    corrupt.loc[corrupt["season"] >= 2024, "pass_matchup"] = 9.0
    refit = fit_season(corrupt, ["pass_matchup"], 2024, scale=7.0, window=4, half_life=2.0, lambdas=(0.01,))
    assert fit.train_seasons == refit.train_seasons
    assert max(fit.train_seasons) == 2023
    assert fit.beta == pytest.approx(refit.beta)
    assert fit.mean == pytest.approx(refit.mean)


def test_promotion_requires_both_check_seasons():
    good = {"2024": {"hits": 10, "n": 12, "brier": 0.2}, "2025": {"hits": 11, "n": 12, "brier": 0.2}}
    base = {"2024": {"hits": 8, "n": 12, "brier": 0.22}, "2025": {"hits": 8, "n": 12, "brier": 0.22}}
    one_year = {"2024": {"hits": 10, "n": 12, "brier": 0.2}, "2025": {"hits": 8, "n": 12, "brier": 0.2}}
    worse_brier = {"2024": {"hits": 10, "n": 12, "brier": 0.3}, "2025": {"hits": 11, "n": 12, "brier": 0.2}}
    assert beats_both(good, base)
    assert not beats_both(one_year, base)
    assert not beats_both(worse_brier, base)
    assert CHECK_SEASONS == (2024, 2025)


def test_a_real_gap_is_promoted_and_a_later_season_does_not_set_the_weights():
    rng = np.random.default_rng(3)
    frame = _games(range(2017, 2027), slope=8.0, rng=rng, n=80)
    report = evaluate(frame, scale=7.0, features=["pass_matchup"])
    assert report["promoted"]
    assert report["in_the_spread"] == ["pass_matchup"]
    fit_2024 = next(row for row in report["weights_by_season"] if row["season"] == 2024)
    fit_2026 = next(row for row in report["weights_by_season"] if row["season"] == 2026)
    assert max(fit_2024["train_seasons"]) == 2023
    assert 2026 not in fit_2024["train_seasons"]
    assert max(fit_2026["train_seasons"]) == 2025
    dynamic_2024 = report["accuracy"]["dynamic"]["2024"]
    base_2024 = report["accuracy"]["baseline"]["2024"]
    assert dynamic_2024["hits"] > base_2024["hits"]
    assert dynamic_2024["brier"] < base_2024["brier"]


def test_positive_spread_line_picks_the_home_team():
    frame = pd.DataFrame({
        "season": [2024, 2024, 2024],
        "margin": [7.0, -3.0, 6.0],
        "spread_line": [3.0, 3.0, 0.0],
    })
    scored = closing_line_scores(frame, [2024])
    assert scored["2024"] == {"hits": 1, "n": 2}


def test_published_screen_keeps_scrimmage_epa_and_the_page_quotes_it():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "nflrankings" / "aspect_screen.json").read_text())
    text = (root / "docs" / "methodology.html").read_text()
    assert report["promoted"] is False
    assert report["in_the_spread"] == []
    assert report["check_seasons"] == [2024, 2025]
    fit_2024 = next(row for row in report["weights_by_season"] if row["season"] == 2024)
    fit_2026 = next(row for row in report["weights_by_season"] if row["season"] == 2026)
    assert max(fit_2024["train_seasons"]) == 2023
    assert max(fit_2026["train_seasons"]) == 2025
    assert report["accuracy"]["baseline"]["2026"]["hits"] == 73
    assert report["accuracy"]["baseline"]["2026"]["n"] == 120
    assert report["closing_line"]["2026"]["hits"] == 79
    for year in ("2024", "2025"):
        assert report["accuracy"]["dynamic"][year]["hits"] < report["accuracy"]["baseline"][year]["hits"]
        assert f"{report['accuracy']['dynamic'][year]['hits']} of {report['accuracy']['dynamic'][year]['n']}" in text
        assert f"{report['accuracy']['baseline'][year]['hits']} of {report['accuracy']['baseline'][year]['n']}" in text
    assert "75 of 120" in text
    assert "73 of 120" in text
    assert "four seasons" in text


def test_constant_feature_adds_nothing_to_the_baseline():
    frame = _games(range(2018, 2025), slope=0.0, rng=np.random.default_rng(4), n=60)
    frame["pass_matchup"] = 0.0
    fit = fit_season(frame, ["pass_matchup"], 2024, scale=7.0, lambdas=(1.0,))
    assert fit.features == ()
    assert apply_fit(frame, fit) == pytest.approx(frame["base"].to_numpy())
