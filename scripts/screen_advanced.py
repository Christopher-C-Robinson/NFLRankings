#!/usr/bin/env python3
"""Walk-forward screen of drive, special-teams, and related rates.

The published pregame spread is schedule-adjusted scrimmage EPA, blended with
last season at 14 games. This script asks whether other nflverse rates should
be added. It fits each added point weight on 2018–2023 only, then reports
2024, 2025, and 2026. It does not write docs/data.

Usage:
  python scripts/screen_advanced.py
  python scripts/screen_advanced.py --cache /tmp/nflverse

Cache files are games.csv and pbp_{year}.parquet from the nflverse-data
releases. The script downloads a missing file. It does not need a paid API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nflrankings.rating import adjust  # noqa: E402
from nflrankings.schedule import BLEND_PRIOR_GAMES, blend_v2, shrink_prior_v2  # noqa: E402
from nflrankings.units import (  # noqa: E402
    drive_points_observations,
    drive_start_observations,
    explosive_observations,
    special_teams_observations,
    success_observations,
)
from nflrankings.winprob import load_conversion, win_probability  # noqa: E402

RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
YEARS = range(2017, 2027)
PLAY_COLS = [
    "season_type", "week", "game_id", "play_id", "posteam", "defteam", "play_type",
    "epa", "success", "yards_gained", "yardline_100", "two_point_attempt", "fixed_drive",
    "posteam_score", "posteam_score_post",
]


def _download(url: str, dest: Path) -> None:
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"download {dest.name}", flush=True)
    urllib.request.urlretrieve(url, dest)


def _ensure(cache: Path) -> None:
    games = cache / "games.csv"
    if not games.exists():
        _download(f"{RELEASE}/schedules/games.csv", games)
    for year in YEARS:
        path = cache / f"pbp_{year}.parquet"
        if not path.exists():
            _download(f"{RELEASE}/pbp/play_by_play_{year}.parquet", path)


def _schedule(cache: Path) -> pd.DataFrame:
    sched = pd.read_csv(cache / "games.csv")
    sched = sched[sched["game_type"].eq("REG") & sched["season"].between(2017, 2026)].copy()
    sched["week"] = pd.to_numeric(sched["week"])
    sched["neutral"] = sched["location"].eq("Neutral")
    return sched[sched["home_score"].notna() & sched["away_score"].notna()]


def _plays(cache: Path, year: int) -> pd.DataFrame:
    frame = pq.read_table(cache / f"pbp_{year}.parquet", columns=PLAY_COLS).to_pandas()
    frame = frame[frame["season_type"].eq("REG")].copy()
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    return frame


def _scrimmage_epa(plays: pd.DataFrame) -> pd.DataFrame:
    two = pd.to_numeric(plays["two_point_attempt"], errors="coerce").fillna(0)
    keep = (
        plays["play_type"].isin(["pass", "run"])
        & plays["posteam"].notna()
        & plays["defteam"].notna()
        & plays["epa"].notna()
        & two.ne(1)
    )
    out = plays.loc[keep, ["week", "posteam", "defteam", "epa"]].copy()
    out["epa"] = out["epa"].astype(float)
    return out


def _net(frame: pd.DataFrame, teams: list[str]) -> dict[str, float]:
    if frame.empty or frame["posteam"].nunique() < 2 or frame["defteam"].nunique() < 2:
        return {team: 0.0 for team in teams}
    rated = adjust(frame[["posteam", "defteam", "epa"]]).reindex(teams)
    return {team: 0.0 if pd.isna(rated.loc[team, "v2"]) else float(rated.loc[team, "v2"]) for team in teams}


def _score(actual: np.ndarray, margin: np.ndarray, scale: float) -> tuple[int, int, float]:
    decisive = actual != 0
    graded = decisive & (margin != 0)
    hits = int(((margin > 0) == (actual > 0))[graded].sum())
    n = int(graded.sum())
    prob = np.array([win_probability(float(value), scale) for value in margin])
    y = (actual > 0).astype(float)
    brier = float(np.mean((prob[decisive] - y[decisive]) ** 2)) if decisive.any() else float("nan")
    return hits, n, brier


def _fmt(hits: int, n: int, brier: float) -> str:
    rate = hits / n if n else float("nan")
    return f"{hits}/{n} {rate:.1%} Brier {brier:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="screen_advanced")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "nflrankings-screen")
    args = parser.parse_args()
    _ensure(args.cache)
    params = load_conversion()
    epa_to_points = float(params["epa_to_points"])
    home_field = float(params["home_field_points"])
    scale = float(params["win_prob_scale"])
    sched = _schedule(args.cache)

    features: dict[int, dict[str, pd.DataFrame]] = {}
    print("loading plays", flush=True)
    for year in YEARS:
        plays = _plays(args.cache, year)
        features[year] = {
            "epa": _scrimmage_epa(plays),
            "st": special_teams_observations(plays),
            "start_fp": drive_start_observations(plays),
            "success": success_observations(plays),
            "explosive": explosive_observations(plays),
            "ppd": drive_points_observations(plays),
        }
        print(f"  {year} drives {len(features[year]['ppd'])} st {len(features[year]['st'])}", flush=True)

    counts = {}
    finals = {year: {} for year in YEARS}
    for year in YEARS:
        played = sched[sched["season"].eq(year)]
        teams = sorted(set(played["home_team"]) | set(played["away_team"]))
        counts[year] = {team: 0 for team in teams}
        for row in played.itertuples(index=False):
            counts[year][row.home_team] += 1
            counts[year][row.away_team] += 1
        for name, frame in features[year].items():
            finals[year][name] = _net(frame, teams)

    names = ["epa", "st", "start_fp", "success", "explosive", "ppd"]
    rows = []
    for year in range(2018, 2027):
        played_games = sched[sched["season"].eq(year)]
        teams = sorted(set(played_games["home_team"]) | set(played_games["away_team"]))
        priors = {
            name: {team: shrink_prior_v2(finals[year - 1][name].get(team, 0.0), counts[year - 1].get(team, 0)) for team in teams}
            for name in names
        }
        played_n = {team: 0 for team in teams}
        for week in sorted(int(value) for value in played_games["week"].unique()):
            raw = {}
            live = {}
            for name in names:
                before = features[year][name]
                before = before[before["week"] < week]
                current = _net(before, teams)
                raw[name] = current
                live[name] = {
                    team: blend_v2(current[team], priors[name].get(team, 0.0), played_n[team], BLEND_PRIOR_GAMES)
                    for team in teams
                }
            for game in played_games[played_games["week"].eq(week)].itertuples(index=False):
                record = {
                    "season": year,
                    "week": int(game.week),
                    "margin": float(game.home_score) - float(game.away_score),
                    "home_flag": 0.0 if game.neutral else 1.0,
                    "live_h": raw["epa"][game.home_team],
                    "live_a": raw["epa"][game.away_team],
                    "prior_h": priors["epa"].get(game.home_team, 0.0),
                    "prior_a": priors["epa"].get(game.away_team, 0.0),
                    "n_h": played_n[game.home_team],
                    "n_a": played_n[game.away_team],
                }
                for name in names:
                    record[name] = live[name][game.home_team] - live[name][game.away_team]
                rows.append(record)
            for game in played_games[played_games["week"].eq(week)].itertuples(index=False):
                played_n[game.home_team] += 1
                played_n[game.away_team] += 1
        print(f"rated {year}", flush=True)

    df = pd.DataFrame(rows)
    df["base"] = epa_to_points * df["epa"] + home_field * df["home_flag"]

    def report(label: str, margin: np.ndarray) -> None:
        print(label)
        for year in range(2018, 2027):
            mask = df["season"].eq(year).to_numpy()
            hits, n, brier = _score(df.loc[mask, "margin"].to_numpy(), margin[mask], scale)
            extra = ""
            if year == 2026:
                early = mask & df["week"].le(4).to_numpy()
                late = mask & df["week"].ge(5).to_numpy()
                eh, en, eb = _score(df.loc[early, "margin"].to_numpy(), margin[early], scale)
                lh, ln, lb = _score(df.loc[late, "margin"].to_numpy(), margin[late], scale)
                extra = f"  early {_fmt(eh, en, eb)}  late {_fmt(lh, ln, lb)}"
            print(f"  {year} {_fmt(hits, n, brier)}{extra}")

    print("\nBaseline: scrimmage EPA, k=14")
    report("baseline", df["base"].to_numpy())

    print("\nAdded rates. Weight is the mean of the 2018–2023 season slopes, then checked later.")
    for name in ("st", "start_fp", "success", "explosive", "ppd"):
        betas = []
        for year in range(2018, 2024):
            part = df[df["season"].eq(year)]
            x = part[name].to_numpy()
            target = (part["margin"] - part["base"]).to_numpy()
            denom = float(np.dot(x, x))
            betas.append(0.0 if denom < 1e-12 else float(np.dot(x, target) / denom))
        beta = float(np.mean(betas))
        print(f"\n{name} mean slope {beta:+.3f} season slopes {[round(value, 2) for value in betas]}")
        report(name, df["base"].to_numpy() + beta * df[name].to_numpy())

    print("\nPrior length on scrimmage EPA only. k=14 is the published blend.")
    for k in (8, 12, 14):
        margin = np.array([
            epa_to_points * (
                blend_v2(row.live_h, row.prior_h, row.n_h, k) - blend_v2(row.live_a, row.prior_a, row.n_a, k)
            ) + home_field * row.home_flag
            for row in df.itertuples(index=False)
        ])
        pooled = df["season"].between(2018, 2024).to_numpy()
        hits, n, brier = _score(df.loc[pooled, "margin"].to_numpy(), margin[pooled], scale)
        print(f"k={k} 2018–2024 {_fmt(hits, n, brier)}")
        report(f"k={k}", margin)


if __name__ == "__main__":
    main()
