"""Pass/rush splits, weekly ratings, and schedule projections. No network."""

import pandas as pd
import pytest

from nflrankings.pipeline import align_abbr, build_teams, enrich_games
from nflrankings.schedule import weekly_v2

PARAMS = {
    "epa_to_points": 40.0,
    "home_field_points": 2.0,
    "win_prob_scale": 10.0,
    "margin_residual_sd": 12.0,
}


def _plays():
    rows = []

    def add(week, off, dfn, epa, kind, n=6):
        rows.extend(
            dict(season_type="REG", week=week, posteam=off, defteam=dfn, play_type=kind, epa=epa, two_point_attempt=0)
            for _ in range(n)
        )

    add(1, "AA", "BB", 0.40, "pass")
    add(1, "BB", "AA", -0.20, "run")
    add(1, "BB", "AA", 0.00, "pass")
    add(1, "AA", "BB", 0.10, "run")
    add(2, "AA", "BB", -0.50, "pass", n=12)
    add(2, "BB", "AA", 0.30, "run", n=12)
    return pd.DataFrame(rows)


def _sched():
    return pd.DataFrame([
        dict(game_type="REG", week=1, home_team="AA", away_team="BB", home_score=24, away_score=10, location="Home"),
        dict(game_type="REG", week=2, home_team="BB", away_team="AA", home_score=None, away_score=None, location="Neutral"),
    ])


def _desc():
    return pd.DataFrame([
        dict(team_abbr="AA", team_name="Alpha", team_conf="AFC", team_division="AFC East",
             team_color="#112233", team_color2="#abcdef", team_logo_espn="https://example.com/aa.png"),
        dict(team_abbr="BB", team_name="Beta", team_conf="NFC", team_division="NFC East",
             team_color="#445566", team_color2="#000000", team_logo_espn="https://example.com/bb.png"),
    ])


def test_weekly_rating_changes_when_later_plays_are_included():
    series = weekly_v2(_plays(), ["AA", "BB"])
    assert [point["week"] for point in series["AA"]] == [1, 2]
    assert series["AA"][0]["v2"] != pytest.approx(series["AA"][1]["v2"])


def test_pass_and_rush_are_separate_and_schedule_splits_one_win():
    teams = build_teams(_plays(), _sched(), _desc(), PARAMS)
    alpha = next(t for t in teams if t["team"] == "AA")
    assert alpha["off_pass_plays"] > 0 and alpha["off_rush_plays"] > 0
    assert alpha["off_pass_epa_adj"] != pytest.approx(alpha["off_rush_epa_adj"])
    assert len(alpha["weeks"]) == 2
    games, ppg = enrich_games(teams, _sched(), PARAMS, {"AA", "BB"})
    assert len(games) == 2
    aa = next(t for t in teams if t["team"] == "AA")
    bb = next(t for t in teams if t["team"] == "BB")
    assert games[0]["played"]
    assert 0 <= games[0]["proj_home"] < 60
    assert 0 <= games[0]["proj_away"] < 60
    assert games[0]["spread_home"] == pytest.approx(40 * (aa["v2"] - bb["v2"]) + 2, abs=1e-3)
    assert not games[1]["played"] and games[1]["neutral"]
    assert ppg == pytest.approx(34 / 2)
    expected = sum(t["schedule_expected_wins"] for t in teams)
    assert expected == pytest.approx(2)
    alpha = next(t for t in teams if t["team"] == "AA")
    assert alpha["projected_wins"] == pytest.approx(alpha["wins"] + (1 - games[1]["home_win_chance"]), abs=5e-4)
    assert alpha["sos"] == pytest.approx(next(t["v2"] for t in teams if t["team"] == "BB"))
    assert align_abbr("AA", {"AA"}) == "AA"
