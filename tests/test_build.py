"""Offline team build: win chance and team metadata."""

import pandas as pd
import pytest

from nflrankings.pipeline import align_abbr, build_teams, records
from nflrankings.winprob import average_win_chances

PARAMS = {
    "method": "epa-spread-logistic-v1",
    "ranking": "neutral-round-robin",
    "epa_to_points": 40.0,
    "home_field_points": 2.0,
    "win_prob_scale": 10.0,
}


def _pbp():
    rows = []

    def add(off, dfn, epa, n=12, season_type="REG"):
        rows.extend(
            dict(season_type=season_type, week=1, posteam=off, defteam=dfn, play_type="run", epa=epa, two_point_attempt=0)
            for _ in range(n)
        )

    add("LA", "GB", 0.30)
    add("GB", "LA", -0.10)
    add("CHI", "LA", 0.00)
    add("LA", "CHI", 0.10)
    add("GB", "CHI", 0.05)
    add("CHI", "GB", -0.20)
    add("LA", "GB", 9.0, n=3, season_type="POST")
    return pd.DataFrame(rows)


def _sched():
    return pd.DataFrame([
        dict(game_type="REG", home_team="LAR", away_team="GB", home_score=27, away_score=14, location="Home"),
        dict(game_type="REG", home_team="GB", away_team="CHI", home_score=20, away_score=20, location="Neutral"),
        dict(game_type="POST", home_team="LA", away_team="GB", home_score=40, away_score=0, location="Home"),
    ])


def _desc():
    return pd.DataFrame([
        dict(team_abbr="LA", team_name="Los Angeles Rams", team_conf="NFC", team_division="NFC West",
             team_color="#003594", team_color2="#ffa300", team_logo_espn="https://example.com/la.png",
             team_logo_wikipedia="https://example.com/la-wiki.png"),
        dict(team_abbr="GB", team_name="Green Bay Packers", team_conf="NFC", team_division="NFC North",
             team_color="red", team_color2="#000000", team_logo_espn="javascript:alert(1)",
             team_logo_wikipedia="https://example.com/gb.png"),
        dict(team_abbr="CHI", team_name="Chicago Bears", team_conf="NFC", team_division="NFC North",
             team_color="#112233", team_color2="", team_logo_espn="", team_logo_wikipedia="http://insecure.example/chi.png"),
    ])


def test_align_abbr_follows_the_rating_index():
    assert align_abbr("LAR", {"LA"}) == "LA"
    assert align_abbr("LA", {"LAR"}) == "LAR"
    assert align_abbr("STL", {"STL"}) == "STL"
    assert align_abbr("KC", {"KC"}) == "KC"
    assert align_abbr("NOPE", {"KC"}) is None


def test_build_teams_ranks_by_win_chance_and_drops_bad_metadata():
    teams = build_teams(_pbp(), _sched(), _desc(), PARAMS)
    assert [t["team"] for t in teams][0] == "LA"
    assert [t["win_chance_rank"] for t in teams] == [1, 2, 3]
    assert teams[0]["v2"] == max(t["v2"] for t in teams)
    chances = average_win_chances({t["team"]: t["v2"] for t in teams}, 40, 10)
    for team in teams:
        assert team["win_chance"] == pytest.approx(chances[team["team"]]["win_chance"], abs=5e-7)
        assert team["opponents"] == 2
        assert 0 < team["win_chance"] < 1
        for banned in ("leg" + "acy", "off_" + "function", "def_" + "function", "components"):
            assert banned not in team
    rams = next(t for t in teams if t["team"] == "LA")
    packers = next(t for t in teams if t["team"] == "GB")
    bears = next(t for t in teams if t["team"] == "CHI")
    assert rams["name"] == "Los Angeles Rams"
    assert rams["logo"] == "https://example.com/la.png"
    assert rams["color"] == "#003594"
    assert rams["color2"] == "#FFA300"
    assert rams["wins"] == 1 and rams["losses"] == 0 and rams["point_diff"] == 13
    assert packers["logo"] == "https://example.com/gb.png"
    assert packers["color"] == ""
    assert packers["wins"] == 0 and packers["losses"] == 1 and packers["ties"] == 1
    assert packers["point_diff"] == -13
    assert bears["logo"] == ""
    assert bears["wins"] == 0 and bears["ties"] == 1 and bears["point_diff"] == 0


def test_postseason_scores_do_not_count():
    rec = records(_sched(), {"LA", "GB", "CHI"})
    assert rec.loc["LA", "wins"] == 1
    assert rec.loc["LA", "point_diff"] == 13
    assert rec.loc["GB", "losses"] == 1 and rec.loc["GB", "ties"] == 1
