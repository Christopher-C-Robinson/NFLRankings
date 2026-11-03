"""Hierarchical division and conference power. No network."""

import pytest

from nflrankings.group_power import (
    DIVISION_PRIOR_TEAMS,
    MARGIN_CAP,
    TEAM_PRIOR_GAMES,
    attach_group_power,
    fit_group_power,
)


def _objective(teams, games, home_field, powers):
    """The documented hierarchy objective, written out for the optimality check."""
    team_prior = TEAM_PRIOR_GAMES
    division_weight = TEAM_PRIOR_GAMES * DIVISION_PRIOR_TEAMS
    conference_weight = division_weight * 1.0
    total = 0.0
    for game in games:
        if not game.get("played"):
            continue
        margin = float(game["home_score"]) - float(game["away_score"])
        margin = max(-MARGIN_CAP, min(MARGIN_CAP, margin))
        venue = 0.0 if game.get("neutral") else home_field
        adjusted = margin - venue
        home = powers[game["home"]]["power"]
        away = powers[game["away"]]["power"]
        total += (adjusted - home + away) ** 2
    seen_divisions = {}
    for team in teams:
        info = powers[team["team"]]
        target = 0.0 if not info["division"] else info["division_power"]
        total += team_prior * (info["power"] - target) ** 2
        if info["division"]:
            seen_divisions[info["division"]] = info["conference_power"] if info["conference"] else 0.0
    seen_conferences = set()
    for division, conference_power in seen_divisions.items():
        # division_power is shared; read it from any member.
        members = [powers[team["team"]]["division_power"] for team in teams if powers[team["team"]]["division"] == division]
        division_power = members[0]
        total += division_weight * (division_power - conference_power) ** 2
        if conference_power != 0.0 or any(powers[team["team"]]["conference"] for team in teams if powers[team["team"]]["division"] == division):
            conference = next(powers[team["team"]]["conference"] for team in teams if powers[team["team"]]["division"] == division)
            if conference:
                seen_conferences.add((conference, conference_power))
    for _name, points in seen_conferences:
        total += conference_weight * points ** 2
    return total


def test_no_games_stay_at_the_zero_prior():
    teams = [
        {"team": "A", "division": "AFC East", "conference": "AFC"},
        {"team": "B", "division": "AFC East", "conference": "AFC"},
    ]
    fit = fit_group_power(teams, [], 1.78)
    assert fit["team_powers"]["A"]["power"] == pytest.approx(0.0, abs=1e-9)
    assert fit["team_powers"]["A"]["division_power"] == pytest.approx(0.0, abs=1e-9)
    assert fit["team_powers"]["A"]["conference_power"] == pytest.approx(0.0, abs=1e-9)
    assert fit["diagnostics"]["objective"] == pytest.approx(0.0, abs=1e-9)


def test_blowout_lifts_the_winning_division_and_conference():
    teams = [
        {"team": "H", "division": "AFC East", "conference": "AFC"},
        {"team": "A", "division": "NFC East", "conference": "NFC"},
    ]
    games = [{"home": "H", "away": "A", "home_score": 40, "away_score": 0, "neutral": True, "played": True}]
    fit = fit_group_power(teams, games, 0.0)
    home = fit["team_powers"]["H"]
    away = fit["team_powers"]["A"]
    assert home["power"] > away["power"]
    assert home["division_power"] > away["division_power"]
    assert home["conference_power"] > away["conference_power"]
    # The cap is ±28, so a 40-point game does not enter as 40.
    assert fit["margin_cap"] == 28
    assert home["division"] == "AFC East"


def test_home_edge_is_removed_before_the_fit():
    teams = [
        {"team": "H", "division": "AFC East", "conference": "AFC"},
        {"team": "A", "division": "NFC East", "conference": "NFC"},
    ]
    tied = [{"home": "H", "away": "A", "home_score": 2, "away_score": 0, "neutral": False, "played": True}]
    fit = fit_group_power(teams, tied, 2.0)
    # Margin 2 minus home edge 2 is a pick, so the ratings stay at the prior.
    assert fit["team_powers"]["H"]["power"] == pytest.approx(0.0, abs=1e-8)
    assert fit["team_powers"]["A"]["power"] == pytest.approx(0.0, abs=1e-8)


def test_independent_is_not_pooled():
    teams = [
        {"team": "I", "division": "", "conference": "Independent"},
        {"team": "H", "division": "AFC East", "conference": "AFC"},
    ]
    games = [{"home": "H", "away": "I", "home_score": 21, "away_score": 7, "neutral": True, "played": True}]
    fit = fit_group_power(teams, games, 0.0)
    indie = fit["team_powers"]["I"]
    assert indie["division"] is None
    assert indie["division_power"] == pytest.approx(0.0)
    assert indie["conference_power"] == pytest.approx(0.0)
    assert [row["name"] for row in fit["conferences"]] == ["AFC"]
    assert fit["division_prior_teams"] == 0.5
    assert fit["team_prior_games"] == 2


def test_solution_beats_nearby_ratings():
    teams = [
        {"team": "H", "division": "AFC East", "conference": "AFC"},
        {"team": "M", "division": "AFC East", "conference": "AFC"},
        {"team": "A", "division": "NFC East", "conference": "NFC"},
    ]
    games = [
        {"home": "H", "away": "A", "home_score": 27, "away_score": 14, "neutral": False, "played": True},
        {"home": "M", "away": "H", "home_score": 17, "away_score": 20, "neutral": True, "played": True},
        {"home": "A", "away": "M", "home_score": 10, "away_score": 24, "neutral": False, "played": False},
    ]
    fit = fit_group_power(teams, games, 1.5)
    base = _objective(teams, games, 1.5, fit["team_powers"])
    assert base == pytest.approx(fit["diagnostics"]["objective"], rel=1e-6, abs=1e-6)
    for abbr in ("H", "M", "A"):
        for bump in (-0.4, 0.4):
            moved = {name: dict(row) for name, row in fit["team_powers"].items()}
            moved[abbr]["power"] = moved[abbr]["power"] + bump
            assert _objective(teams, games, 1.5, moved) > base


def test_conflicting_division_membership_is_an_error():
    teams = [
        {"team": "A", "division": "East", "conference": "AFC"},
        {"team": "B", "division": "East", "conference": "NFC"},
    ]
    with pytest.raises(ValueError, match="more than one conference"):
        fit_group_power(teams, [], 0.0)


def test_attach_copies_powers_onto_teams_without_replacing_v2():
    teams = [
        {"team": "H", "division": "AFC East", "conference": "AFC", "v2": 0.2},
        {"team": "A", "division": "NFC East", "conference": "NFC", "v2": -0.1},
    ]
    games = [{"home": "H", "away": "A", "home_score": 24, "away_score": 17, "neutral": True, "played": True}]
    summary = attach_group_power(teams, games, 0.0)
    assert teams[0]["v2"] == 0.2
    assert "hierarchy_power" in teams[0]
    assert summary["definition"] == "hierarchy-power-1"
    assert summary["divisions"][0]["teams"] >= 1
    assert "holdout" in summary["tuning"]
    assert "0.5" in summary["tuning"]
