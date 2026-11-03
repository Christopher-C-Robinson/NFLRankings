"""EPA margin to point spread and win probability. No I/O.

The board rank is a neutral-site round robin, the same summary College Football
Index uses: each team's score is its average win chance against every other
team. Home field is fit and available for a single game, and it is not added
inside that round robin.

The logistic of a rating difference is strictly increasing, and every team
plays the same kind of game, so this order matches the schedule-adjusted EPA
order. The percentage is still the average of the win chances, which is not
the win chance against an average team.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

CONVERSION_PATH = Path(__file__).with_name("conversion.json")
_REQUIRED = ("epa_to_points", "home_field_points", "win_prob_scale")


def load_conversion(path: Path = CONVERSION_PATH) -> dict:
    """Load the shipped EPA-to-spread fit. Weekly refreshes do not refit it."""
    data = json.loads(path.read_text())
    for key in _REQUIRED:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"conversion {key} must be a finite number")
    if data["epa_to_points"] <= 0 or data["win_prob_scale"] <= 0:
        raise ValueError("epa_to_points and win_prob_scale must be positive")
    return data


def win_probability(point_margin: float, win_prob_scale: float) -> float:
    """Logistic P(the side with ``point_margin`` wins).

    ``P = 1 / (1 + exp(-point_margin / win_prob_scale))``. A margin of 0 is 1/2.
    """
    scale = float(win_prob_scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("win_prob_scale must be a positive finite number")
    z = float(point_margin) / scale
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def point_spread(epa_diff: float, epa_to_points: float, home_field_points: float = 0.0) -> float:
    """Points for the first side: ``epa_to_points * epa_diff + home_field_points``.

    ``epa_diff`` is that side's schedule-adjusted EPA/play minus the opponent's.
    Pass ``home_field_points=0`` for a neutral site.
    """
    return float(epa_to_points) * float(epa_diff) + float(home_field_points)


def predict_matchup(
    rating_a: float,
    rating_b: float,
    params: Mapping[str, float],
    venue: str = "neutral",
) -> dict:
    """One deterministic game from team A's perspective.

    ``venue`` is ``neutral``, ``a_home``, or ``b_home``. This is the hook a
    later matchup view can call. It does not simulate draws.
    """
    if venue not in ("neutral", "a_home", "b_home"):
        raise ValueError("venue must be neutral, a_home, or b_home")
    hfa = float(params["home_field_points"])
    bump = {"neutral": 0.0, "a_home": hfa, "b_home": -hfa}[venue]
    margin = point_spread(float(rating_a) - float(rating_b), float(params["epa_to_points"]), bump)
    return {
        "venue": venue,
        "margin": margin,
        "win_probability": win_probability(margin, float(params["win_prob_scale"])),
    }


def _logistic_matrix(margin: np.ndarray, scale: float) -> np.ndarray:
    z = np.asarray(margin, dtype=float) / float(scale)
    # Symmetric clip: clip(z) and clip(-z) stay negations, so P_ij + P_ji = 1.
    z = np.clip(z, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-z))


def average_win_chances(
    ratings: Mapping[str, float],
    epa_to_points: float,
    win_prob_scale: float,
) -> dict[str, dict]:
    """Neutral round robin. Each value is against the other teams only.

    Home field is intentionally absent. Keys: ``win_chance``, ``mean_margin``,
    ``expected_wins``, ``opponents``.
    """
    if float(epa_to_points) <= 0 or float(win_prob_scale) <= 0:
        raise ValueError("scales must be positive")
    teams = sorted(ratings)
    if len(teams) < 2:
        raise ValueError("need at least two teams")
    strength = np.array([float(ratings[team]) for team in teams], dtype=float)
    if not np.isfinite(strength).all():
        raise ValueError("ratings must be finite")
    diff = strength[:, None] - strength[None, :]
    margin = float(epa_to_points) * diff
    prob = _logistic_matrix(margin, win_prob_scale)
    np.fill_diagonal(prob, np.nan)
    np.fill_diagonal(margin, np.nan)
    opponents = len(teams) - 1
    out = {}
    for i, team in enumerate(teams):
        out[team] = {
            "win_chance": float(np.nanmean(prob[i])),
            "mean_margin": float(np.nanmean(margin[i])),
            "expected_wins": float(np.nansum(prob[i])),
            "opponents": opponents,
        }
    return out


def apply_ranks(rows: list[dict]) -> list[dict]:
    """Set ``win_chance_rank`` and ``v2_rank`` on each row, best = 1.

    Win-chance ties break on mean neutral margin, then team name, then
    abbreviation, so display rounding never decides the order. Ranks are the
    full-field order. Callers that hide rows must keep these numbers.
    """
    needed = ("team", "name", "v2", "win_chance", "mean_margin")
    for row in rows:
        missing = [key for key in needed if key not in row]
        if missing:
            raise ValueError(f"row missing {missing}")
    ordered = sorted(rows, key=lambda r: (-r["win_chance"], -r["mean_margin"], r["name"], r["team"]))
    for index, row in enumerate(ordered, start=1):
        row["win_chance_rank"] = index
    by_epa = sorted(rows, key=lambda r: (-r["v2"], r["name"], r["team"]))
    for index, row in enumerate(by_epa, start=1):
        row["v2_rank"] = index
    rows.sort(key=lambda r: (r["win_chance_rank"], r["team"]))
    return rows


def apply_win_chances(rows: list[dict], params: Mapping[str, float]) -> list[dict]:
    """Fill round-robin win chances from each row's ``v2`` and then rank."""
    ratings = {row["team"]: row["v2"] for row in rows}
    stats = average_win_chances(ratings, params["epa_to_points"], params["win_prob_scale"])
    for row in rows:
        row.update(stats[row["team"]])
    return apply_ranks(rows)


def fit_margin(
    epa_diff: Sequence[float],
    margin: Sequence[float],
    home_indicator: Sequence[float],
) -> dict:
    """OLS ``margin = home_field * home_indicator + epa_to_points * epa_diff``.

    Neutral games use ``home_indicator`` 0, so they inform the slope only.
    There is no extra intercept. Raises if the EPA slope is not positive.
    """
    x = np.asarray(epa_diff, dtype=float)
    y = np.asarray(margin, dtype=float)
    home = np.asarray(home_indicator, dtype=float)
    if not (len(x) == len(y) == len(home)) or len(x) < 3:
        raise ValueError("need at least three aligned games")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(home).all():
        raise ValueError("fit inputs must be finite")
    if not np.isin(home, (0.0, 1.0)).all():
        raise ValueError("home_indicator must be 0 or 1")
    design = np.column_stack([home, x])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    hfa, scale = float(beta[0]), float(beta[1])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("EPA-to-points slope was not positive")
    pred = design @ beta
    resid = y - pred
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    sd = math.sqrt(ss_res / (len(x) - 2))
    return {
        "home_field_points": hfa,
        "epa_to_points": scale,
        "margin_r2": r2,
        "margin_residual_sd": sd,
        "games": int(len(x)),
    }


def fit_win_prob_scale(spreads: Sequence[float], home_won: Sequence[float]) -> float:
    """MLE logistic scale for ``P(home win) = logistic(spread / scale)``.

    ``home_won`` is 1 or 0. Ties must already be removed. Scale is positive.
    """
    margin = np.asarray(spreads, dtype=float)
    won = np.asarray(home_won, dtype=float)
    if len(margin) != len(won) or len(margin) < 3:
        raise ValueError("need at least three decisive games")
    if not np.isfinite(margin).all() or not np.isin(won, (0.0, 1.0)).all():
        raise ValueError("win/loss fit inputs must be finite 0/1 outcomes")

    def nll(log_scale: float) -> float:
        scale = math.exp(log_scale)
        z = np.clip(margin / scale, -60.0, 60.0)
        log_p = -np.logaddexp(0.0, -z)
        log_q = -np.logaddexp(0.0, z)
        return float(-(won * log_p + (1.0 - won) * log_q).sum())

    # Golden section on log(scale). NFL spreads land well inside (1, 40).
    lo, hi = math.log(1.0), math.log(40.0)
    gr = (math.sqrt(5) - 1) / 2
    c, d = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fc, fd = nll(c), nll(d)
    for _ in range(80):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - gr * (hi - lo)
            fc = nll(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + gr * (hi - lo)
            fd = nll(d)
    scale = math.exp((lo + hi) / 2)
    # Reject a bound solution. A flat likelihood means the games do not identify a scale.
    if scale < 1.05 or scale > 38.0:
        raise ValueError(f"win-probability scale {scale:.3f} sat on the search boundary")
    return scale
