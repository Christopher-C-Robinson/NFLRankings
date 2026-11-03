"""Fit the shipped EPA → point spread → win-chance conversion.

Uses each completed season's own schedule-adjusted EPA (the same v2 rating
the board publishes) and that season's final scores. This is a descriptive
conversion of the rating, not a pre-game forecast. The weekly refresh does
not run this module.

Usage: python -m nflrankings.fit_history --first 2016 --last 2025
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .aggregate import epa_plays
from .pipeline import align_abbr, download_pbp, download_schedule
from .rating import adjust
from .winprob import CONVERSION_PATH, fit_margin, fit_win_prob_scale, point_spread, win_probability


def _games_for_season(season: int, sched) -> dict:
    """Return fit rows for one completed regular season."""
    pbp = download_pbp(season)
    if pbp.empty:
        raise SystemExit(f"no play-by-play for {season}")
    ratings = adjust(epa_plays(pbp))
    del pbp
    known = set(ratings.index)
    games = sched[(sched["season"] == season) & (sched["game_type"] == "REG")].copy()
    games = games[games["home_score"].notna() & games["away_score"].notna()]
    kept = {"epa_diff": [], "margin": [], "home": [], "neutral": 0, "dropped": 0, "ties": 0}
    for row in games.itertuples(index=False):
        home = align_abbr(row.home_team, known)
        away = align_abbr(row.away_team, known)
        if home is None or away is None or home == away:
            kept["dropped"] += 1
            continue
        loc = getattr(row, "location", None)
        neutral = isinstance(loc, str) and loc == "Neutral"
        margin = float(row.home_score) - float(row.away_score)
        kept["epa_diff"].append(float(ratings.loc[home, "v2"] - ratings.loc[away, "v2"]))
        kept["margin"].append(margin)
        kept["home"].append(0.0 if neutral else 1.0)
        kept["neutral"] += int(neutral)
        kept["ties"] += int(margin == 0)
    if len(kept["margin"]) < 3:
        raise SystemExit(f"not enough played games for {season}")
    print(
        f"{season}: {len(kept['margin'])} games, {kept['neutral']} neutral, "
        f"{kept['ties']} ties, {kept['dropped']} dropped"
    )
    return kept


def fit_seasons(first: int, last: int) -> dict:
    """Fit on inclusive regular seasons and return the conversion document."""
    if last < first:
        raise SystemExit("--last must be >= --first")
    years = list(range(first, last + 1))
    import nfl_data_py as nfl

    try:
        sched = nfl.import_schedules(years)
    except Exception as exc:  # noqa: BLE001
        print(f"multi-year schedule import failed ({exc}); loading year by year")
        import pandas as pd

        sched = pd.concat([download_schedule(year) for year in years], ignore_index=True)
    parts = [_games_for_season(year, sched) for year in years]
    epa_diff = np.concatenate([np.asarray(p["epa_diff"]) for p in parts])
    margin = np.concatenate([np.asarray(p["margin"]) for p in parts])
    home = np.concatenate([np.asarray(p["home"]) for p in parts])
    fitted = fit_margin(epa_diff, margin, home)
    spread = np.array([
        point_spread(e, fitted["epa_to_points"], fitted["home_field_points"] * h)
        for e, h in zip(epa_diff, home)
    ])
    decisive = margin != 0
    scale = fit_win_prob_scale(spread[decisive], (margin[decisive] > 0).astype(float))
    probs = np.array([win_probability(s, scale) for s in spread[decisive]])
    home_rate = float((margin[decisive] > 0).mean())

    def r(value, digits=6):
        value = float(value)
        if not math.isfinite(value):
            raise SystemExit("non-finite fit")
        return round(value, digits)

    return {
        "method": "epa-spread-logistic-v1",
        "ranking": "neutral-round-robin",
        "fit_seasons_first": first,
        "fit_seasons_last": last,
        "fit_games": int(len(margin)),
        "fit_ties": int(sum(p["ties"] for p in parts)),
        "neutral_games": int(sum(p["neutral"] for p in parts)),
        "dropped_games": int(sum(p["dropped"] for p in parts)),
        "epa_to_points": r(fitted["epa_to_points"]),
        "home_field_points": r(fitted["home_field_points"]),
        "win_prob_scale": r(scale),
        "margin_r2": r(fitted["margin_r2"]),
        "margin_residual_sd": r(fitted["margin_residual_sd"]),
        "home_win_rate": r(home_rate, 4),
        "mean_predicted_home_win": r(float(probs.mean()), 4),
        "source": "nflverse regular-season finals via nfl_data_py, described by each season's full-season v2 rating",
    }


def main() -> None:
    """Fit and write ``conversion.json``."""
    parser = argparse.ArgumentParser(prog="nflrankings.fit_history")
    parser.add_argument("--first", type=int, default=2016)
    parser.add_argument("--last", type=int, default=2025)
    parser.add_argument("--out", default=str(CONVERSION_PATH))
    args = parser.parse_args()
    doc = fit_seasons(args.first, args.last)
    if not 20 <= doc["epa_to_points"] <= 120:
        raise SystemExit(f"epa_to_points {doc['epa_to_points']} is outside 20–120; not writing")
    if not -1 <= doc["home_field_points"] <= 6:
        raise SystemExit(f"home_field_points {doc['home_field_points']} is outside -1–6; not writing")
    if not 5 <= doc["win_prob_scale"] <= 25:
        raise SystemExit(f"win_prob_scale {doc['win_prob_scale']} is outside 5–25; not writing")
    if doc["fit_games"] < 1000:
        raise SystemExit(f"only {doc['fit_games']} games; not writing")
    path = Path(args.out)
    path.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
