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
