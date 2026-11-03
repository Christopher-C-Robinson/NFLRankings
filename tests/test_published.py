"""Shipped docs/data matches the win-chance conversion and has no old fields."""

import json
import math
from pathlib import Path

import pytest

from nflrankings.winprob import average_win_chances, load_conversion

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"


def _load(name):
    return json.loads((DATA / name).read_text())


def test_methodology_quotes_the_shipped_fit():
    conv = load_conversion()
    text = (ROOT / "docs" / "methodology.html").read_text()
    assert "{{" not in text
    three = 1 / (1 + math.exp(-3 / conv["win_prob_scale"]))
    # Match the page's rounding, not a second copy of the prose.
    for snippet in (
        f"{conv['epa_to_points']:.2f}",
        f"{conv['home_field_points']:.2f}",
        f"{conv['win_prob_scale']:.2f}",
        f"{conv['margin_r2']:.3f}",
        f"{conv['margin_residual_sd']:.2f}",
        f"{conv['home_win_rate'] * 100:.1f}%",
        f"{conv['mean_predicted_home_win'] * 100:.1f}%",
        f"{three * 100:.1f}%",
        str(conv["fit_games"]),
        str(conv["fit_ties"]),
        str(conv["neutral_games"]),
        str(conv["fit_seasons_first"]),
        str(conv["fit_seasons_last"]),
    ):
        assert snippet in text


def test_published_seasons_recompute():
    conv = load_conversion()
    index = _load("index.json")
    assert index["seasons"]
    assert index["ranking"] == "neutral-round-robin"
    for season in index["seasons"]:
        payload = _load(f"{season}.json")
        assert payload["season"] == season
        rank = payload["ranking"]
        for key in ("epa_to_points", "home_field_points", "win_prob_scale", "fit_games"):
            assert rank[key] == conv[key]
        teams = payload["teams"]
        assert len(teams) == 32
        assert [t["win_chance_rank"] for t in teams] == list(range(1, 33))
        ratings = {t["team"]: t["v2"] for t in teams}
        stats = average_win_chances(ratings, conv["epa_to_points"], conv["win_prob_scale"])
        chances = [t["win_chance"] for t in teams]
        assert chances == sorted(chances, reverse=True)
        for team in teams:
            assert team["win_chance"] == pytest.approx(stats[team["team"]]["win_chance"], abs=5e-7)
            assert team["opponents"] == 31
            assert team["logo"].startswith("https://")
            assert len(team["color"]) == 7 and team["color"].startswith("#")
            assert team["conference"] in ("AFC", "NFC")
            assert team["division"].startswith(team["conference"])
        # The logistic round robin does not reorder EPA.
        by_epa = sorted(teams, key=lambda t: (-t["v2"], t["name"], t["team"]))
        assert [t["team"] for t in by_epa] == [t["team"] for t in teams]
        assert payload["games"]
        assert "pregame_home_win_chance" in payload["games"][0]
        assert "wins_above_expected" in teams[0]
        assert teams[0]["weeks"]
        assert teams[0]["off_pass_plays"] > 0
        assert payload["week_calendar"] in ("wednesday-tuesday", "nflverse-week")
        unplayed = [game["week"] for game in payload["games"] if not game["played"]]
        expected_week = min(unplayed) if unplayed else payload["week_max"]
        assert payload["current_week"] == expected_week
        assert payload["current_week_reason"] == ("unplayed" if unplayed else "week_max")
        power = payload["group_power"]
        assert power["definition"] == "hierarchy-power-1"
        assert power["team_prior_games"] == 2
        assert power["division_prior_teams"] == 0.5
        assert power["conference_prior_divisions"] == 1
        assert {row["name"] for row in power["conferences"]} == {"AFC", "NFC"}
        assert len(power["divisions"]) == 8
        assert all(row["teams"] == 4 for row in power["divisions"])
        for team in teams:
            assert "hierarchy_power" in team
            assert "division_power" in team
            assert "conference_power" in team
        if payload["week_calendar"] == "wednesday-tuesday":
            dated = [row for row in payload["weeks"] if row.get("dated_games")]
            assert dated
            assert all(row["aligned"] for row in dated)
            assert all(row["start"] for row in dated)
