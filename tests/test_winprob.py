"""Win-probability math. No network."""

import math

import numpy as np
import pytest

from nflrankings.winprob import (
    MARGIN_Z80,
    apply_ranks,
    apply_win_chances,
    average_win_chances,
    fit_margin,
    fit_win_prob_scale,
    load_conversion,
    margin_interval,
    point_spread,
    predict_matchup,
    project_game,
    projected_total,
    win_probability,
)

PARAMS = {"epa_to_points": 50.0, "home_field_points": 2.5, "win_prob_scale": 12.0}


def test_zero_margin_is_even():
    assert win_probability(0, 12) == pytest.approx(0.5)
    assert win_probability(10, 12) > 0.5
    assert win_probability(-10, 12) == pytest.approx(1 - win_probability(10, 12))


def test_win_probability_rejects_bad_scale():
    with pytest.raises(ValueError):
        win_probability(1, 0)
    with pytest.raises(ValueError):
        win_probability(1, -3)


def test_point_spread_adds_home_field():
    neutral = point_spread(0.1, 50)
    home = point_spread(0.1, 50, home_field_points=2.5)
    assert neutral == pytest.approx(5)
    assert home - neutral == pytest.approx(2.5)


def test_predict_matchup_is_antisymmetric():
    home = predict_matchup(0.2, -0.05, PARAMS, "a_home")
    swapped = predict_matchup(-0.05, 0.2, PARAMS, "b_home")
    assert home["margin"] == pytest.approx(-swapped["margin"])
    assert home["win_probability"] == pytest.approx(1 - swapped["win_probability"])
    neutral = predict_matchup(0.2, -0.05, PARAMS, "neutral")
    assert neutral["margin"] == pytest.approx(point_spread(0.25, 50))
    with pytest.raises(ValueError):
        predict_matchup(0, 0, PARAMS, "home")


def test_round_robin_splits_every_game_and_ignores_home_field():
    ratings = {"A": 0.20, "B": 0.00, "C": -0.10, "D": 0.05}
    stats = average_win_chances(ratings, PARAMS["epa_to_points"], PARAMS["win_prob_scale"])
    expected = sum(row["expected_wins"] for row in stats.values())
    assert expected == pytest.approx(len(ratings) * (len(ratings) - 1) / 2)
    assert all(row["opponents"] == 3 for row in stats.values())
    # Higher EPA has a higher average win chance. Home field is not an input.
    order = sorted(stats, key=lambda team: stats[team]["win_chance"], reverse=True)
    assert order == ["A", "D", "B", "C"]
    # Mean margin is the neutral spread against the other ratings, not a home spread.
    others = [ratings[t] for t in ratings if t != "A"]
    assert stats["A"]["mean_margin"] == pytest.approx(50 * (ratings["A"] - np.mean(others)))


def test_win_chance_order_matches_epa_order():
    ratings = {f"T{i:02d}": (i - 16) * 0.01 for i in range(32)}
    stats = average_win_chances(ratings, 55, 13)
    by_chance = sorted(stats, key=lambda team: stats[team]["win_chance"])
    by_epa = sorted(ratings, key=lambda team: ratings[team])
    assert by_chance == by_epa


def test_ranks_use_full_field_and_name_tie_break():
    rows = [
        {"team": "B", "name": "Bravo", "v2": 1.0, "win_chance": 0.5, "mean_margin": 0.0, "conference": "AFC"},
        {"team": "A", "name": "Alpha", "v2": 1.0, "win_chance": 0.5, "mean_margin": 0.0, "conference": "NFC"},
        {"team": "C", "name": "Charlie", "v2": 0.0, "win_chance": 0.2, "mean_margin": -1.0, "conference": "AFC"},
    ]
    apply_ranks(rows)
    by_team = {row["team"]: row["win_chance_rank"] for row in rows}
    assert by_team == {"A": 1, "B": 2, "C": 3}
    shown = [row["win_chance_rank"] for row in rows if row["conference"] == "AFC"]
    assert shown == [2, 3]


def test_apply_win_chances_ranks_best_epa_first():
    rows = [
        {"team": "Z", "name": "Zulu", "v2": -0.1},
        {"team": "A", "name": "Alpha", "v2": 0.2},
    ]
    apply_win_chances(rows, PARAMS)
    assert rows[0]["team"] == "A"
    assert rows[0]["win_chance_rank"] == 1
    assert rows[0]["win_chance"] > 0.5
    assert rows[1]["win_chance"] == pytest.approx(1 - rows[0]["win_chance"])


def test_margin_fit_recovers_home_field_and_slope():
    epa = np.array([-0.2, -0.1, 0.0, 0.1, 0.2, 0.15, -0.05, 0.3])
    home = np.array([1, 1, 1, 1, 0, 0, 0, 1], dtype=float)
    margin = 2.25 * home + 48 * epa
    fitted = fit_margin(epa, margin, home)
    assert fitted["home_field_points"] == pytest.approx(2.25)
    assert fitted["epa_to_points"] == pytest.approx(48)
    assert fitted["margin_r2"] == pytest.approx(1)


def test_margin_fit_rejects_negative_slope():
    with pytest.raises(ValueError):
        fit_margin([0.2, -0.2, 0.1, -0.1], [0, 5, 1, 4], [1, 1, 1, 1])


def test_logistic_scale_recovers():
    rng = np.random.default_rng(7)
    spreads = rng.uniform(-28, 28, size=6000)
    truth = 12.5
    prob = 1 / (1 + np.exp(-spreads / truth))
    won = rng.random(len(spreads)) < prob
    scale = fit_win_prob_scale(spreads, won.astype(float))
    assert scale == pytest.approx(truth, rel=0.05)
    assert math.isfinite(scale)


def test_margin_range_and_projected_score():
    low, high = margin_interval(3, 10)
    assert low == pytest.approx(3 - MARGIN_Z80 * 10)
    assert high == pytest.approx(3 + MARGIN_Z80 * 10)
    assert high - low == pytest.approx(2 * MARGIN_Z80 * 10)
    total = projected_total(30, 20, 8, 10, 30, 8, 22)
    assert total == pytest.approx(44.6666666667)
    cold = projected_total(0, 0, 0, 0, 0, 0, 22)
    assert cold == pytest.approx(44)
    game = project_game(
        0.2, 0.0, {**PARAMS, "margin_residual_sd": 10}, "a_home",
        {"points_for": 200, "points_against": 160, "games": 8},
        {"points_for": 160, "points_against": 200, "games": 8},
        22,
    )
    assert game["score_a"] + game["score_b"] == pytest.approx(game["total"])
    assert game["margin"] > point_spread(0.2, 50)
    assert game["margin_low"] < game["margin"] < game["margin_high"]
    assert game["win_probability"] > 0.5


def test_shipped_conversion_is_usable():
    doc = load_conversion()
    assert doc["ranking"] == "neutral-round-robin"
    assert doc["epa_to_points"] > 0
    assert doc["win_prob_scale"] > 0
    assert math.isfinite(doc["home_field_points"])
