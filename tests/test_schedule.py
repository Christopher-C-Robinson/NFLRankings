"""Pass/rush splits, weekly ratings, and schedule projections. No network."""

import pandas as pd
import pytest

from nflrankings.pipeline import align_abbr, build_teams, enrich_games, ensure_prior_season
from nflrankings.schedule import blend_v2, prior_ratings_from_teams, shrink_prior_v2, weekly_v2

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


def test_blend_weight_moves_from_prior_to_live_across_five_weeks():
    prior = 0.20
    # Live is held at zero so the leftover prior share is 1 - blended/prior.
    share = [blend_v2(0.0, prior, games) / prior for games in range(6)]
    assert share[0] == pytest.approx(1.0)  # week 1, no games yet
    assert share[1] == pytest.approx(0.80)  # week 2, one game: still mostly prior
    assert share[2] == pytest.approx(4 / 6)  # week 3
    assert share[3] == pytest.approx(4 / 7)  # week 4, mixed
    assert share[4] == pytest.approx(0.50)  # week 5: live has caught the prior
    assert share[5] < 0.50  # the next game makes the live rating the larger part


def test_prior_shrinks_toward_the_league_average():
    raw = 0.247087
    shrunk = shrink_prior_v2(raw, 17)
    assert shrunk == pytest.approx(raw * 17 / (17 + 14))
    assert abs(shrunk) < abs(raw)
    assert shrink_prior_v2(0.0, 17) == 0.0
    assert shrink_prior_v2(raw, 0) == 0.0
    loaded = prior_ratings_from_teams([
        {"team": "LA", "v2": raw, "wins": 12, "losses": 5, "ties": 0},
    ])
    assert loaded["LA"] == pytest.approx(shrunk)


def test_pregame_blends_prior_without_using_the_week_itself():
    from nflrankings.aggregate import rated_plays
    from nflrankings.rating import adjust

    teams = build_teams(_plays(), _sched(), _desc(), PARAMS)
    prior = {"AA": 0.20, "BB": -0.10}
    games, _ppg = enrich_games(teams, _sched(), PARAMS, {"AA", "BB"}, _plays(), prior)
    week1, week2 = games
    # No live plays yet: the whole gap is the shrunk prior, plus home field.
    assert week1["pregame_spread_home"] == pytest.approx(40 * (0.20 - (-0.10)) + 2)
    plays = rated_plays(_plays())
    live = adjust(plays[plays["week"] < 2][["posteam", "defteam", "epa"]])
    blended_home = blend_v2(float(live.loc["BB", "v2"]), prior["BB"], 1)
    blended_away = blend_v2(float(live.loc["AA", "v2"]), prior["AA"], 1)
    mixed = 40 * (blended_home - blended_away)
    assert week2["neutral"]
    assert week2["pregame_spread_home"] == pytest.approx(mixed)
    pure_live = 40 * (float(live.loc["BB", "v2"]) - float(live.loc["AA", "v2"]))
    pure_prior = 40 * (prior["BB"] - prior["AA"])
    assert mixed != pytest.approx(pure_live)
    assert mixed != pytest.approx(pure_prior)


def test_missing_prior_file_is_materialized_once(tmp_path, monkeypatch):
    import json

    payload = {
        "season": 2025,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "ranking": {"ranking": "neutral-round-robin"},
        "teams": [{"team": "LA", "v2": 0.20, "wins": 17, "losses": 0, "ties": 0, "name": "Rams"}],
    }
    calls = []

    def fake_build(season, params=None, *, out_dir=None, fetch_prior=True):
        calls.append((season, fetch_prior))
        assert fetch_prior is False
        return payload

    monkeypatch.setattr("nflrankings.pipeline.build_season", fake_build)
    first = ensure_prior_season(2026, tmp_path, {})
    assert calls == [(2025, False)]
    assert first["LA"] == pytest.approx(0.20 * 17 / 31)
    assert json.loads((tmp_path / "2025.json").read_text())["season"] == 2025
    # A second 2026 build reads the file and does not build 2025 again.
    second = ensure_prior_season(2026, tmp_path, {})
    assert calls == [(2025, False)]
    assert second == first


def test_pregame_ignores_the_week_being_predicted():
    teams = build_teams(_plays(), _sched(), _desc(), PARAMS)
    games, _ppg = enrich_games(teams, _sched(), PARAMS, {"AA", "BB"}, _plays())
    week1, week2 = games
    # No prior plays: the home spread is only home field.
    assert week1["pregame_spread_home"] == pytest.approx(PARAMS["home_field_points"])
    # Week 2 is neutral, so a zero rating gap would be a pick. Week 1 plays move it.
    assert week2["neutral"]
    assert week2["pregame_spread_home"] != pytest.approx(0)
    # The huge week-2 plays must not be inside the week-2 pregame rating.
    # Rebuilding week 2 from week-1 plays only is the contract; the sign follows AA's week-1 edge
    # from the away side because BB is the designated home team.
    assert "wins_above_expected" in teams[0]
    played = [g for g in games if g["played"]]
    home = next(t for t in teams if t["team"] == played[0]["home"])
    assert home["wins_above_expected"] == pytest.approx(home["wins"] - played[0]["pregame_home_win_chance"], abs=5e-4)
    assert align_abbr("AA", {"AA"}) == "AA"
