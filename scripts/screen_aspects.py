#!/usr/bin/env python3
"""Walk-forward screen of every pregame aspect the open files support.

The published spread stays on schedule-adjusted scrimmage EPA unless the
dynamic ridge raises decisive winners on both 2024 and 2025 without raising
Brier. 2026 is printed and is not used to choose the window, the penalty,
or the feature list. The script does not write docs/data.

Usage:
  python scripts/screen_aspects.py
  python scripts/screen_aspects.py --from-cache

Cache files come from the nflverse-data releases: games.csv, pbp_{year}.parquet,
injuries_{year}.parquet, and depth_charts_{year}.parquet. No paid API.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from bisect import bisect_left
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nflrankings.aspects import (  # noqa: E402
    FEATURE_NAMES,
    adjust_components,
    evaluate,
    expected_starter,
    haversine_miles,
    report_on_or_before,
    unit_matchup,
)
from nflrankings.rating import adjust  # noqa: E402
from nflrankings.schedule import PRIOR_SHRINK_GAMES, blend_v2, shrink_prior_v2  # noqa: E402
from nflrankings.units import (  # noqa: E402
    competitive_epa_observations,
    drive_clean_observations,
    drive_points_observations,
    drive_score_observations,
    drive_start_observations,
    early_down_observations,
    explosive_observations,
    late_down_observations,
    pass_epa_observations,
    penalty_observations,
    pressure_observations,
    redzone_observations,
    rush_epa_observations,
    sack_observations,
    scrimmage_epa_observations,
    special_teams_observations,
    success_observations,
    turnover_observations,
    yards_observations,
)
from nflrankings.winprob import load_conversion, shrink_rate  # noqa: E402

RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
# Ratings and game rows. Passer careers also use every earlier pbp file in the cache.
RATING_YEARS = range(2016, 2027)
PLAY_COLS = [
    "season_type", "week", "game_id", "play_id", "posteam", "defteam", "play_type",
    "epa", "success", "yards_gained", "yardline_100", "down", "wp", "two_point_attempt",
    "fixed_drive", "fixed_drive_result", "posteam_score", "posteam_score_post",
    "interception", "fumble_lost", "sack", "qb_hit", "penalty_team", "penalty_yards",
    "passer_player_id",
]
PASSER_COLS = ["season_type", "week", "play_type", "epa", "passer_player_id", "two_point_attempt"]
# Attempts of shrinkage for a starter's career pass EPA. Fixed before the check.
QB_PRIOR_PLAYS = 300
# Passing share shrinks toward this, or toward last season's share, over 100 plays.
PASS_SHARE_ANCHOR = 0.57
PASS_SHARE_PLAYS = 100
# Matchup column -> observation key. The baseline EPA net is separate.
MATCHUPS = {
    "pass_matchup": "pass",
    "rush_matchup": "rush",
    "early_matchup": "early",
    "late_matchup": "late",
    "redzone_matchup": "redzone",
    "comp_matchup": "comp",
    "success_matchup": "success",
    "explosive_matchup": "explosive",
    "ypp_matchup": "yards",
    "turnover_matchup": "turnover",
    "sack_matchup": "sack",
    "pressure_matchup": "pressure",
    "penalty_matchup": "penalty",
    "start_matchup": "start",
    "ppd_matchup": "ppd",
    "score_drive_matchup": "score_drive",
    "clean_drive_matchup": "clean_drive",
    "st_matchup": "st",
}
BUILDERS = {
    "epa": scrimmage_epa_observations,
    "pass": pass_epa_observations,
    "rush": rush_epa_observations,
    "early": early_down_observations,
    "late": late_down_observations,
    "redzone": redzone_observations,
    "comp": competitive_epa_observations,
    "success": success_observations,
    "explosive": explosive_observations,
    "yards": yards_observations,
    "turnover": turnover_observations,
    "sack": sack_observations,
    "pressure": pressure_observations,
    "penalty": penalty_observations,
    "start": drive_start_observations,
    "ppd": drive_points_observations,
    "score_drive": drive_score_observations,
    "clean_drive": drive_clean_observations,
    "st": special_teams_observations,
}
# Approximate public stadium coordinates, not a feed. Relocations are split by season.
SITES = {
    "ARI": (33.5276, -112.2626),
    "ATL": (33.7553, -84.4008),
    "BAL": (39.2780, -76.6227),
    "BUF": (42.7738, -78.7870),
    "CAR": (35.2258, -80.8528),
    "CHI": (41.8623, -87.6167),
    "CIN": (39.0954, -84.5160),
    "CLE": (41.5061, -81.6995),
    "DAL": (32.7473, -97.0945),
    "DEN": (39.7439, -105.0201),
    "DET": (42.3400, -83.0456),
    "GB": (44.5013, -88.0622),
    "HOU": (29.6847, -95.4107),
    "IND": (39.7601, -86.1639),
    "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839),
    "LV": (36.0909, -115.1833),
    "MIA": (25.9580, -80.2389),
    "MIN": (44.9738, -93.2577),
    "NE": (42.0909, -71.2643),
    "NO": (29.9511, -90.0812),
    "NYG": (40.8128, -74.0742),
    "NYJ": (40.8128, -74.0742),
    "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158),
    "SEA": (47.5952, -122.3316),
    "SF": (37.4033, -121.9694),
    "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713),
    "WAS": (38.9076, -76.8645),
    "OAK": (37.7516, -122.2005),
    "SD": (32.7831, -117.1196),
    "LA_COLISEUM": (34.0141, -118.2879),
    "LA_CARSON": (33.8644, -118.2611),
    "LA_SOFI": (33.9535, -118.3392),
}
NEUTRAL_SITES = {
    # Domestic sites that the schedule sometimes marks Neutral. Same buildings as the club sites.
    "Acrisure Stadium": (40.4468, -80.0158),
    "FirstEnergy Stadium": (41.5061, -81.6995),
    "Ford Field": (42.3400, -83.0456),
    "Hard Rock Stadium": (25.9580, -80.2389),
    "Lucas Oil Stadium": (39.7601, -86.1639),
    "MetLife Stadium": (40.8128, -74.0742),
    "SoFi Stadium": (33.9535, -118.3392),
    "State Farm Stadium": (33.5276, -112.2626),
    "TIAA Bank Stadium": (30.3239, -81.6373),
    "Wembley Stadium": (51.5560, -0.2795),
    "Tottenham Stadium": (51.6042, -0.0662),
    "Tottenham Hotspur Stadium": (51.6042, -0.0662),
    "Twickenham Stadium": (51.4559, -0.3415),
    "Azteca Stadium": (19.3029, -99.1505),
    "Estadio Banorte": (19.3029, -99.1505),
    "Deutsche Bank Park": (50.0686, 8.6455),
    "Allianz Arena": (48.2188, 11.6247),
    "FC Bayern Munich Stadium": (48.2188, 11.6247),
    "Arena Corinthians": (-23.5453, -46.4742),
    "Maracana Stadium": (-22.9122, -43.2302),
    "Melbourne Cricket Ground": (-37.8200, 144.9834),
    "Stade de France": (48.9244, 2.3601),
    "Bernabeu": (40.4531, -3.6883),
}
OMITTED = [
    {
        "name": "snap counts",
        "reason": "The snap file is a postgame count. Last week's snaps are already inside the next week's EPA, so they are not a separate pregame input.",
    },
    {
        "name": "closing spread, moneyline, and total",
        "reason": "Market numbers. The closing spread is scored as a comparison and is not a feature.",
    },
    {
        "name": "current-game participation",
        "reason": "Who played the snaps is known after the game. The screen uses the depth chart and the injury report instead.",
    },
    {
        "name": "coaches, referees, and division flags",
        "reason": "They are on the schedule. A separate flag per coach would memorize clubs. They are not aspect weights.",
    },
    {
        "name": "relocation priors",
        "reason": "Oakland's 2019 rating is not copied onto Las Vegas in 2020, and San Diego is not copied onto the Chargers. Those week-1 handoffs stay at the league rate. The published EPA blend does the same.",
    },
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
    for year in list(range(1999, 2016)) + list(RATING_YEARS):
        path = cache / f"pbp_{year}.parquet"
        if not path.exists():
            _download(f"{RELEASE}/pbp/play_by_play_{year}.parquet", path)
    for year in RATING_YEARS:
        injuries = cache / f"injuries_{year}.parquet"
        depth = cache / f"depth_charts_{year}.parquet"
        if not injuries.exists():
            _download(f"{RELEASE}/injuries/injuries_{year}.parquet", injuries)
        if not depth.exists():
            _download(f"{RELEASE}/depth_charts/depth_charts_{year}.parquet", depth)


def _read_plays(path: Path, wanted: list[str]) -> pd.DataFrame:
    import pyarrow.parquet as pq

    have = set(pq.read_schema(path).names)
    columns = [column for column in wanted if column in have]
    frame = pq.read_table(path, columns=columns).to_pandas()
    if "season_type" in frame.columns:
        frame = frame[frame["season_type"].eq("REG")].copy()
    if "week" in frame.columns:
        frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    return frame


def _schedule(cache: Path) -> pd.DataFrame:
    sched = pd.read_csv(cache / "games.csv")
    sched = sched[sched["game_type"].eq("REG") & sched["season"].between(2016, 2026)].copy()
    sched["week"] = pd.to_numeric(sched["week"])
    sched["neutral"] = sched["location"].eq("Neutral")
    return sched[sched["home_score"].notna() & sched["away_score"].notna()].reset_index(drop=True)


def _site(season: int, team: str):
    if team in ("OAK",) or (team == "LV" and season < 2020):
        return SITES["OAK"]
    if team == "SD" or (team == "LAC" and season < 2017):
        return SITES["SD"]
    if team == "LAC":
        return SITES["LA_CARSON"] if season < 2020 else SITES["LA_SOFI"]
    if team == "LA":
        return SITES["LA_COLISEUM"] if season < 2020 else SITES["LA_SOFI"]
    return SITES.get(team)


def _travel(season: int, home: str, away: str, neutral: bool, stadium: str) -> float:
    home_site = _site(season, home)
    away_site = _site(season, away)
    if home_site is None or away_site is None:
        return 0.0
    if neutral:
        spot = NEUTRAL_SITES.get(stadium) or SITES.get(home)
        if spot is None:
            return 0.0
        away_miles = haversine_miles(away_site[0], away_site[1], spot[0], spot[1])
        home_miles = haversine_miles(home_site[0], home_site[1], spot[0], spot[1])
        return (away_miles - home_miles) / 1000.0
    return haversine_miles(away_site[0], away_site[1], home_site[0], home_site[1]) / 1000.0


def _passer_rows(frame: pd.DataFrame) -> dict[tuple[int, int], dict[str, tuple[float, int]]]:
    """(year, week) -> passer id -> (epa sum, plays). The year is attached by the caller via week only.

    This helper is year-agnostic: keys are weeks. The caller stores the year.
    """
    needed = {"week", "play_type", "epa", "passer_player_id"}
    if not needed.issubset(frame.columns):
        return {}
    two = pd.to_numeric(frame["two_point_attempt"], errors="coerce").fillna(0) if "two_point_attempt" in frame.columns else 0
    keep = frame["play_type"].eq("pass") & frame["epa"].notna() & frame["passer_player_id"].notna() & frame["week"].notna()
    if not isinstance(two, int):
        keep = keep & two.ne(1)
    plays = frame.loc[keep]
    if plays.empty:
        return {}
    grouped = plays.groupby(["week", "passer_player_id"])["epa"].agg(total="sum", n="size")
    out: dict[int, dict[str, tuple[float, int]]] = {}
    for (week, player_id), row in grouped.iterrows():
        out.setdefault(int(week), {})[str(player_id)] = (float(row["total"]), int(row["n"]))
    return out


def _load_observations(cache: Path) -> tuple[dict, dict, dict]:
    """Per-year aspect rows, passer totals, and play counts."""
    observations: dict[int, dict[str, pd.DataFrame]] = {}
    passers: dict[tuple[int, int], dict[str, tuple[float, int]]] = {}
    counts: dict[int, dict[str, int]] = {}
    for year in range(1999, 2027):
        path = cache / f"pbp_{year}.parquet"
        if not path.exists():
            continue
        if year in RATING_YEARS:
            plays = _read_plays(path, PLAY_COLS)
            observations[year] = {}
            for name, builder in BUILDERS.items():
                observations[year][name] = builder(plays)
            week_passers = _passer_rows(plays)
            counts[year] = {name: int(len(frame)) for name, frame in observations[year].items()}
            print(f"plays {year} scrimmage {counts[year].get('epa', 0)} drives {counts[year].get('ppd', 0)}", flush=True)
            del plays
        else:
            week_passers = _passer_rows(_read_plays(path, PASSER_COLS))
        for week, players in week_passers.items():
            passers[(year, week)] = players
    return observations, passers, counts


def _gameday_map(sched: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for record in sched.itertuples(index=False):
        day = pd.to_datetime(record.gameday, errors="coerce")
        day = None if pd.isna(day) else day.date()
        rows.append({"season": int(record.season), "week": int(record.week), "team": record.home_team, "gameday": day})
        rows.append({"season": int(record.season), "week": int(record.week), "team": record.away_team, "gameday": day})
    return pd.DataFrame(rows).drop_duplicates(["season", "week", "team"])


def _load_availability(cache: Path, sched: pd.DataFrame) -> dict:
    """Injury outs and quarterback ladders. Daily charts use the previous day's snapshot."""
    days = _gameday_map(sched)
    injury_frames = []
    weekly: dict[tuple[int, int, str], list[str]] = {}
    daily: dict[str, dict] = {}
    for year in RATING_YEARS:
        injury_path = cache / f"injuries_{year}.parquet"
        if injury_path.exists():
            frame = pd.read_parquet(injury_path)
            if "game_type" in frame.columns:
                frame = frame[frame["game_type"].eq("REG")]
            injury_frames.append(frame)
        depth_path = cache / f"depth_charts_{year}.parquet"
        if not depth_path.exists():
            continue
        depth = pd.read_parquet(depth_path)
        if "club_code" in depth.columns and "position" in depth.columns:
            chart = depth[depth["position"].eq("QB")].copy()
            if "game_type" in chart.columns:
                chart = chart[chart["game_type"].eq("REG")]
            if "formation" in chart.columns:
                chart = chart[chart["formation"].eq("Offense")]
            chart["week"] = pd.to_numeric(chart["week"], errors="coerce")
            chart["rank"] = pd.to_numeric(chart["depth_team"], errors="coerce").fillna(99)
            chart = chart[chart["week"].notna() & chart["gsis_id"].notna() & chart["club_code"].notna()]
            chart = chart.sort_values("rank")
            for (season, week, team), part in chart.groupby(["season", "week", "club_code"], sort=False):
                ladder = []
                for player_id in part["gsis_id"]:
                    player_id = str(player_id)
                    if player_id not in ladder:
                        ladder.append(player_id)
                weekly[(int(season), int(week), str(team))] = ladder
        elif "pos_abb" in depth.columns:
            chart = depth[depth["pos_abb"].eq("QB") & depth["gsis_id"].notna() & depth["team"].notna()].copy()
            chart["ts"] = pd.to_datetime(chart["dt"], utc=True, errors="coerce")
            chart = chart[chart["ts"].notna()]
            chart["day"] = chart["ts"].dt.date
            chart["rank"] = pd.to_numeric(chart["pos_rank"], errors="coerce").fillna(99)
            latest = chart.groupby(["team", "day"])["ts"].transform("max")
            chart = chart[chart["ts"].eq(latest)].sort_values(["team", "day", "rank"])
            chart = chart.drop_duplicates(["team", "day", "gsis_id"])
            for (team, day), part in chart.groupby(["team", "day"], sort=False):
                daily.setdefault(str(team), {})[day] = [str(player_id) for player_id in part["gsis_id"]]
    daily_dates = {team: sorted(days_for_team) for team, days_for_team in daily.items()}
    outs: dict[tuple[int, int, str], set[str]] = {}
    out_count: dict[tuple[int, int, str], int] = {}
    injury_rows = 0
    if injury_frames:
        injuries = pd.concat(injury_frames, ignore_index=True)
        injuries["week"] = pd.to_numeric(injuries["week"], errors="coerce")
        injuries = injuries[injuries["week"].notna() & injuries["gsis_id"].notna() & injuries["team"].notna()].copy()
        injuries["week"] = injuries["week"].astype(int)
        injuries["season"] = injuries["season"].astype(int)
        injuries = injuries.merge(days, on=["season", "week", "team"], how="left")
        if "date_modified" in injuries.columns:
            modified = pd.to_datetime(injuries["date_modified"], utc=True, errors="coerce")
            keep = [
                report_on_or_before(None if pd.isna(stamp) else stamp.date(), game_date)
                for stamp, game_date in zip(modified, injuries["gameday"])
            ]
            injuries = injuries.loc[keep].sort_values("date_modified")
        injuries = injuries.drop_duplicates(["season", "week", "team", "gsis_id"], keep="last")
        injury_rows = int(len(injuries))
        status = injuries["report_status"].fillna("").astype(str).str.strip()
        position = injuries["position"].fillna("").astype(str).str.strip() if "position" in injuries.columns else ""
        unavailable = injuries[status.isin(["Out", "Doubtful"])]
        for record in unavailable.itertuples(index=False):
            outs.setdefault((int(record.season), int(record.week), str(record.team)), set()).add(str(record.gsis_id))
        ruled_out = injuries[status.isin(["Out"]) & ~position.isin(["K", "P", "LS"])]
        for (season, week, team), part in ruled_out.groupby(["season", "week", "team"]):
            out_count[(int(season), int(week), str(team))] = int(part["gsis_id"].nunique())
    return {
        "weekly": weekly,
        "daily": daily,
        "daily_dates": daily_dates,
        "outs": outs,
        "out_count": out_count,
        "injury_rows": injury_rows,
    }


def _ladder(personnel: dict, season: int, week: int, team: str, gameday) -> list[str]:
    dates = personnel["daily_dates"].get(team, [])
    if dates and gameday is not None:
        index = bisect_left(dates, gameday) - 1
        if index >= 0:
            return personnel["daily"][team][dates[index]]
    return personnel["weekly"].get((season, week, team), [])


def _mean(values: pd.Series) -> float:
    if values is None or len(values) == 0 or not values.notna().any():
        return 0.0
    return float(values.mean())


def _components_before(frame: pd.DataFrame, week: int) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["off_adj", "def_adj", "off_n", "def_n"])
    before = frame[frame["week"] < week]
    if before.empty:
        return pd.DataFrame(columns=["off_adj", "def_adj", "off_n", "def_n"])
    return adjust_components(before)


def _blend_side(live: float, prior: float, games: int, league: float) -> float:
    if not math.isfinite(live):
        live = league
    if not math.isfinite(prior):
        prior = league
    return blend_v2(live, prior, games)


def _net_v2(frame: pd.DataFrame, week: int, teams: list[str]) -> dict[str, float]:
    if frame is None or frame.empty:
        return {team: 0.0 for team in teams}
    before = frame[frame["week"] < week]
    if before.empty or before["posteam"].nunique() < 2 or before["defteam"].nunique() < 2:
        return {team: 0.0 for team in teams}
    rated = adjust(before[["posteam", "defteam", "epa"]]).reindex(teams)
    return {team: 0.0 if pd.isna(rated.loc[team, "v2"]) else float(rated.loc[team, "v2"]) for team in teams}


def _final_v2(frame: pd.DataFrame, teams: list[str]) -> dict[str, float]:
    if frame is None or frame.empty or frame["posteam"].nunique() < 2:
        return {team: 0.0 for team in teams}
    rated = adjust(frame[["posteam", "defteam", "epa"]]).reindex(teams)
    return {team: 0.0 if pd.isna(rated.loc[team, "v2"]) else float(rated.loc[team, "v2"]) for team in teams}


def _shrink_components(comp: pd.DataFrame, teams: list[str], games: dict[str, int]) -> dict[str, tuple[float, float]]:
    off_league = _mean(comp["off_adj"]) if len(comp) else 0.0
    def_league = _mean(comp["def_adj"]) if len(comp) else 0.0
    out = {}
    for team in teams:
        if len(comp) and team in comp.index and pd.notna(comp.at[team, "off_adj"]):
            off = float(comp.at[team, "off_adj"])
        else:
            off = off_league
        if len(comp) and team in comp.index and pd.notna(comp.at[team, "def_adj"]):
            deff = float(comp.at[team, "def_adj"])
        else:
            deff = def_league
        played = int(games.get(team, 0))
        out[team] = (
            shrink_rate(off, played, off_league, PRIOR_SHRINK_GAMES),
            shrink_rate(deff, played, def_league, PRIOR_SHRINK_GAMES),
        )
    return out


def _counts_before(frame: pd.DataFrame, week: int) -> dict[str, int]:
    if frame is None or frame.empty:
        return {}
    before = frame[frame["week"] < week]
    if before.empty:
        return {}
    return before.groupby("posteam").size().astype(int).to_dict()


def _share(pass_n: int, scrimmage_n: int, anchor: float) -> float:
    return (pass_n + PASS_SHARE_PLAYS * anchor) / (scrimmage_n + PASS_SHARE_PLAYS)


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def build_games(cache: Path) -> tuple[pd.DataFrame, dict]:
    """One pregame row per played regular-season game, aspects from earlier weeks only."""
    sched = _schedule(cache)
    print("loading plays", flush=True)
    observations, passers, play_counts = _load_observations(cache)
    personnel = _load_availability(cache, sched)
    params = load_conversion()
    epa_to_points = float(params["epa_to_points"])
    home_field = float(params["home_field_points"])
    qb_state: dict[str, list[float]] = {}
    for year in range(1999, 2016):
        weeks = sorted(week for (passer_year, week) in passers if passer_year == year)
        for week in weeks:
            for player_id, (total, n) in passers.get((year, week), {}).items():
                bucket = qb_state.setdefault(player_id, [0.0, 0.0])
                bucket[0] += total
                bucket[1] += n

    prior_v2: dict[str, float] = {}
    prior_games: dict[str, int] = {}
    prior_components: dict[str, dict[str, tuple[float, float]]] = {}
    prior_share: dict[str, float] = {}
    rows = []
    coverage = {
        "team_games": 0,
        "qb_found": 0,
        "starter_compared": 0,
        "starter_agreed": 0,
        "team_games_with_out_row": 0,
        "unknown_neutral_stadiums": [],
    }
    unknown_stadiums: set[str] = set()

    def qb_value(player_id: str | None) -> float:
        if not player_id or player_id not in qb_state:
            return 0.0
        total, n = qb_state[player_id]
        if n <= 0:
            return 0.0
        return total / (n + QB_PRIOR_PLAYS)

    for year in RATING_YEARS:
        played = sched[sched["season"].eq(year)]
        if played.empty or year not in observations:
            continue
        teams = sorted(set(played["home_team"]) | set(played["away_team"]))
        games_played = {team: 0 for team in teams}
        for record in played.itertuples(index=False):
            games_played[record.home_team] += 1
            games_played[record.away_team] += 1
        played_n = {team: 0 for team in teams}
        year_obs = observations[year]
        for week in sorted(int(value) for value in played["week"].unique()):
            live_v2 = _net_v2(year_obs["epa"], week, teams)
            blended_v2 = {
                team: blend_v2(live_v2[team], prior_v2.get(team, 0.0), played_n[team])
                for team in teams
            }
            sides: dict[str, dict[str, tuple[float, float]]] = {}
            for aspect in set(MATCHUPS.values()):
                comp = _components_before(year_obs.get(aspect), week)
                off_league = _mean(comp["off_adj"]) if len(comp) else 0.0
                def_league = _mean(comp["def_adj"]) if len(comp) else 0.0
                stored = prior_components.get(aspect, {})
                side = {}
                for team in teams:
                    if len(comp) and team in comp.index and pd.notna(comp.at[team, "off_adj"]):
                        live_off = float(comp.at[team, "off_adj"])
                    else:
                        live_off = float("nan")
                    if len(comp) and team in comp.index and pd.notna(comp.at[team, "def_adj"]):
                        live_def = float(comp.at[team, "def_adj"])
                    else:
                        live_def = float("nan")
                    prior = stored.get(team, (off_league, def_league))
                    side[team] = (
                        _blend_side(live_off, prior[0], played_n[team], off_league),
                        _blend_side(live_def, prior[1], played_n[team], def_league),
                    )
                sides[aspect] = side
            pass_counts = _counts_before(year_obs.get("pass"), week)
            rush_counts = _counts_before(year_obs.get("rush"), week)
            shares = {}
            for team in teams:
                pass_n = int(pass_counts.get(team, 0))
                scrimmage_n = pass_n + int(rush_counts.get(team, 0))
                shares[team] = _share(pass_n, scrimmage_n, prior_share.get(team, PASS_SHARE_ANCHOR))
            week_games = played[played["week"].eq(week)]
            for game in week_games.itertuples(index=False):
                home = game.home_team
                away = game.away_team
                neutral = bool(game.neutral)
                record = {
                    "season": year,
                    "week": week,
                    "margin": float(game.home_score) - float(game.away_score),
                    "base": epa_to_points * (blended_v2[home] - blended_v2[away]) + (0.0 if neutral else home_field),
                    "spread_line": _finite(getattr(game, "spread_line", None)),
                }
                for name, aspect in MATCHUPS.items():
                    off_home, def_home = sides[aspect][home]
                    off_away, def_away = sides[aspect][away]
                    record[name] = unit_matchup(off_home, def_home, off_away, def_away)
                record["pass_exposed"] = shares[home] * (sides["pass"][home][0] - sides["pass"][away][1]) - shares[away] * (
                    sides["pass"][away][0] - sides["pass"][home][1]
                )
                rush_home = 1.0 - shares[home]
                rush_away = 1.0 - shares[away]
                record["rush_exposed"] = rush_home * (sides["rush"][home][0] - sides["rush"][away][1]) - rush_away * (
                    sides["rush"][away][0] - sides["rush"][home][1]
                )
                home_rest = _finite(getattr(game, "home_rest", None))
                away_rest = _finite(getattr(game, "away_rest", None))
                record["rest_diff"] = 0.0 if home_rest is None or away_rest is None else home_rest - away_rest
                stadium = getattr(game, "stadium", "") or ""
                if neutral and stadium not in NEUTRAL_SITES and stadium not in SITES:
                    unknown_stadiums.add(str(stadium))
                record["travel_diff"] = _travel(year, home, away, neutral, str(stadium))
                wind = _finite(getattr(game, "wind", None)) or 0.0
                temp = _finite(getattr(game, "temp", None))
                cold = 0.0 if temp is None else max(0.0, 45.0 - temp)
                share_gap = shares[away] - shares[home]
                record["wind_pass"] = wind * share_gap
                record["cold_pass"] = cold * share_gap
                gameday = pd.to_datetime(game.gameday, errors="coerce")
                gameday = None if pd.isna(gameday) else gameday.date()
                home_qb = expected_starter(_ladder(personnel, year, week, home, gameday), personnel["outs"].get((year, week, home), set()))
                away_qb = expected_starter(_ladder(personnel, year, week, away, gameday), personnel["outs"].get((year, week, away), set()))
                record["qb_edge"] = qb_value(home_qb) - qb_value(away_qb)
                record["out_diff"] = personnel["out_count"].get((year, week, away), 0) - personnel["out_count"].get((year, week, home), 0)
                rows.append(record)
                coverage["team_games"] += 2
                coverage["qb_found"] += int(home_qb is not None) + int(away_qb is not None)
                if (year, week, home) in personnel["out_count"] or (year, week, home) in personnel["outs"]:
                    coverage["team_games_with_out_row"] += 1
                if (year, week, away) in personnel["out_count"] or (year, week, away) in personnel["outs"]:
                    coverage["team_games_with_out_row"] += 1
                for side, found in ((getattr(game, "home_qb_id", None), home_qb), (getattr(game, "away_qb_id", None), away_qb)):
                    if side is None or (isinstance(side, float) and math.isnan(side)) or str(side) in ("", "nan"):
                        continue
                    coverage["starter_compared"] += 1
                    coverage["starter_agreed"] += int(found is not None and str(side) == found)
            for game in week_games.itertuples(index=False):
                played_n[game.home_team] += 1
                played_n[game.away_team] += 1
            for player_id, (total, n) in passers.get((year, week), {}).items():
                bucket = qb_state.setdefault(player_id, [0.0, 0.0])
                bucket[0] += total
                bucket[1] += n
        final_v2 = _final_v2(year_obs["epa"], teams)
        prior_v2 = {team: shrink_prior_v2(final_v2.get(team, 0.0), games_played.get(team, 0)) for team in teams}
        prior_components = {}
        for aspect in set(MATCHUPS.values()):
            prior_components[aspect] = _shrink_components(adjust_components(year_obs.get(aspect, pd.DataFrame())), teams, games_played)
        prior_share = {}
        for team in teams:
            pass_n = int((year_obs["pass"]["posteam"] == team).sum()) if not year_obs["pass"].empty else 0
            rush_n = int((year_obs["rush"]["posteam"] == team).sum()) if not year_obs["rush"].empty else 0
            prior_share[team] = (pass_n / (pass_n + rush_n)) if (pass_n + rush_n) else PASS_SHARE_ANCHOR
        # Silence an unused prior-games binding. The shrink already consumed the counts.
        del prior_games
        print(f"rated {year}", flush=True)

    coverage["unknown_neutral_stadiums"] = sorted(unknown_stadiums)
    coverage["play_rows"] = {str(year): play_counts.get(year, {}) for year in RATING_YEARS}
    coverage["injury_rows_kept"] = personnel["injury_rows"]
    coverage["weekly_qb_charts"] = len(personnel["weekly"])
    coverage["daily_qb_clubs"] = len(personnel["daily_dates"])
    frame = pd.DataFrame(rows)
    missing = [name for name in FEATURE_NAMES if name not in frame.columns]
    if missing:
        raise SystemExit(f"game table is missing {missing}")
    return frame, coverage


def _print_table(report: dict) -> None:
    print("\nDecisive winners. Ties and exact 50/50 picks are out of the hit rate. Lower Brier is better.")
    for name in ("baseline", "dynamic", "static_frozen"):
        print(f"\n{name}")
        table = report["accuracy"][name]
        for year in sorted(table, key=int):
            row = table[year]
            rate = row["hits"] / row["n"] if row["n"] else float("nan")
            extra = ""
            if "weeks_1_4" in row:
                early = row["weeks_1_4"]
                late = row["weeks_5_plus"]
                extra = (
                    f"  weeks 1-4 {early['hits']}/{early['n']} Brier {early['brier']:.3f}"
                    f"  weeks 5+ {late['hits']}/{late['n']} Brier {late['brier']:.3f}"
                )
            print(f"  {year} {row['hits']}/{row['n']} {rate:.1%} Brier {row['brier']:.3f} MAE {row['mae']:.2f}{extra}")
    print("\nPooled")
    for span, block in report["pooled"].items():
        print(f"  {span}")
        for name, row in block.items():
            rate = row["hits"] / row["n"] if row["n"] else float("nan")
            print(f"    {name} {row['hits']}/{row['n']} {rate:.1%} Brier {row['brier']:.3f}")
    if report.get("closing_line"):
        print("\nClosing line, not an input")
        for year, row in report["closing_line"].items():
            rate = row["hits"] / row["n"] if row["n"] else float("nan")
            print(f"  {year} {row['hits']}/{row['n']} {rate:.1%}")
    print(f"\n{report['decision']}")
    print("Largest |weights| on the 2024 and 2025 fits, in points per standard deviation:")
    for row in report["weight_leaders"][:8]:
        print(f"  {row['name']} {row['mean_abs_beta']:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="screen_aspects")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "nflrankings-screen")
    parser.add_argument("--from-cache", action="store_true", help="reuse aspect_games.parquet in the cache")
    parser.add_argument("--out", type=Path, default=ROOT / "nflrankings" / "aspect_screen.json")
    args = parser.parse_args()
    cache = args.cache
    _ensure(cache)
    table_path = cache / "aspect_games.parquet"
    if args.from_cache and table_path.exists():
        frame = pd.read_parquet(table_path)
        coverage = json.loads((cache / "aspect_coverage.json").read_text()) if (cache / "aspect_coverage.json").exists() else {}
        print(f"loaded {len(frame)} games from cache", flush=True)
    else:
        frame, coverage = build_games(cache)
        frame.to_parquet(table_path, index=False)
        (cache / "aspect_coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
        print(f"saved {len(frame)} games", flush=True)
    scale = float(load_conversion()["win_prob_scale"])
    report = evaluate(frame, scale)
    report["coverage"] = {
        key: coverage.get(key)
        for key in (
            "team_games", "qb_found", "starter_compared", "starter_agreed",
            "team_games_with_out_row", "unknown_neutral_stadiums", "injury_rows_kept",
            "weekly_qb_charts", "daily_qb_clubs",
        )
    }
    report["play_rows"] = coverage.get("play_rows", {})
    report["omitted"] = OMITTED
    report["personnel_rule"] = (
        "Expected starter is the first offense-chart quarterback who is not Out or Doubtful. "
        "Weekly charts are the chart for that week. Daily charts, from 2025 on, use the last snapshot dated before gameday. "
        "Injury rows with a timestamp after gameday are dropped. Seasons whose injury file has no timestamp keep the week's report. "
        "out_diff counts players ruled Out, except kickers, punters, and long snappers. "
        "qb_edge is that starter's career pass EPA from 1999 on, shrunk with 300 prior plays toward zero, home minus away. "
        "Same-week games do not use each other's plays, matching the published EPA week cut."
    )
    report["static_frozen_note"] = (
        "Equal-weight ridge fit on 2018-2023 only, then frozen. Those six seasons are in-sample for the static row. "
        "2024-2026 are a comparison. The static row cannot replace the dynamic model after the check is known."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.out}", flush=True)
    _print_table(report)


if __name__ == "__main__":
    main()
