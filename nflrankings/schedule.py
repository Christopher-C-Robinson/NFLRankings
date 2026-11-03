"""Schedule projections and week-by-week EPA from plays already in memory."""

from __future__ import annotations

import pandas as pd

from .aggregate import rated_plays
from .rating import adjust
from .winprob import project_game

_EMPTY = {"wins": 0, "losses": 0, "ties": 0, "point_diff": 0, "points_for": 0, "points_against": 0}


def _split_ratings(plays: pd.DataFrame, teams: list[str]) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Adjusted EPA for one play type, plus offensive and defensive play counts."""
    if plays.empty:
        empty = pd.DataFrame(0.0, index=teams, columns=["off_epa_adj", "def_epa_adj", "v2"])
        zeros = pd.Series(0, index=teams)
        return empty, zeros, zeros
    frame = plays[["posteam", "defteam", "epa"]]
    # A single team cannot be opponent-adjusted against itself. Keep the raw means.
    if frame["posteam"].nunique() < 2 or frame["defteam"].nunique() < 2:
        off = frame.groupby("posteam")["epa"].mean()
        dfn = frame.groupby("defteam")["epa"].mean()
        rated = pd.DataFrame({"off_epa_adj": off, "def_epa_adj": dfn}).reindex(teams)
        rated["v2"] = rated["off_epa_adj"] - rated["def_epa_adj"]
    else:
        rated = adjust(frame).reindex(teams)
    off_n = plays.groupby("posteam").size().reindex(teams).fillna(0).astype(int)
    def_n = plays.groupby("defteam").size().reindex(teams).fillna(0).astype(int)
    return rated, off_n, def_n


def unit_ratings(pbp: pd.DataFrame, teams: list[str]) -> dict[str, dict]:
    """Schedule-adjusted pass and rush EPA. Missing units stay null."""
    out = {team: {} for team in teams}
    for label, kinds in (("pass", ("pass",)), ("rush", ("run",))):
        rated, off_n, def_n = _split_ratings(rated_plays(pbp, kinds), teams)
        for team in teams:
            plays_off = int(off_n.get(team, 0))
            plays_def = int(def_n.get(team, 0))
            off = rated.loc[team, "off_epa_adj"] if plays_off else None
            dfn = rated.loc[team, "def_epa_adj"] if plays_def else None
            out[team][f"off_{label}_epa_adj"] = None if off is None or pd.isna(off) else float(off)
            out[team][f"def_{label}_epa_adj"] = None if dfn is None or pd.isna(dfn) else float(dfn)
            out[team][f"off_{label}_plays"] = plays_off
            out[team][f"def_{label}_plays"] = plays_def
    return out


def weekly_v2(pbp: pd.DataFrame, teams: list[str]) -> dict[str, list[dict]]:
    """Cumulative schedule-adjusted EPA after each played week."""
    plays = rated_plays(pbp)
    series = {team: [] for team in teams}
    if plays.empty or "week" not in plays.columns:
        return series
    weeks = sorted(int(w) for w in pd.to_numeric(plays["week"], errors="coerce").dropna().unique())
    for week in weeks:
        subset = plays[pd.to_numeric(plays["week"], errors="coerce") <= week]
        if subset.empty:
            continue
        rated = adjust(subset[["posteam", "defteam", "epa"]])
        for team in teams:
            if team not in rated.index:
                continue
            series[team].append({"week": week, "v2": float(rated.loc[team, "v2"])})
    return series


def _scoring(record: dict) -> dict:
    """Per-game points, which is what the shrink expects."""
    games = int(record["wins"]) + int(record["losses"]) + int(record["ties"])
    return {
        "points_for": (int(record["points_for"]) / games) if games else 0.0,
        "points_against": (int(record["points_against"]) / games) if games else 0.0,
        "games": games,
    }


def league_ppg(records: pd.DataFrame) -> float:
    """Points per team per played game. Zero when nobody has played."""
    if records.empty or "points_for" not in records.columns:
        return 0.0
    games = int((records["wins"] + records["losses"] + records["ties"]).sum())
    if games <= 0:
        return 0.0
    # Each game is counted twice, once for each team.
    return float(records["points_for"].sum()) / games


def season_games(sched: pd.DataFrame, teams: list[dict], params: dict, known: set[str], align) -> list[dict]:
    """Regular-season games with a current-rating projection.

    The projection uses the season rating published on the board, so games
    already played are described by a rating that includes them. Frozen
    pregame picks are a separate field.
    """
    by_team = {row["team"]: row for row in teams}
    rows = []
    games = sched[sched["game_type"] == "REG"]
    for record in games.itertuples(index=False):
        home = align(record.home_team, known)
        away = align(record.away_team, known)
        if home is None or away is None or home not in by_team or away not in by_team or home == away:
            continue
        home_score = getattr(record, "home_score", None)
        away_score = getattr(record, "away_score", None)
        played = pd.notna(home_score) and pd.notna(away_score)
        loc = getattr(record, "location", None)
        neutral = isinstance(loc, str) and loc == "Neutral"
        venue = "neutral" if neutral else "a_home"
        proj = project_game(
            by_team[home]["v2"], by_team[away]["v2"], params, venue,
            _scoring(by_team[home]), _scoring(by_team[away]),
            float(params.get("_league_ppg", 0.0)),
        )
        week = getattr(record, "week", None)
        rows.append({
            "week": int(week) if pd.notna(week) else None,
            "home": home,
            "away": away,
            "neutral": neutral,
            "played": bool(played),
            "home_score": int(home_score) if played else None,
            "away_score": int(away_score) if played else None,
            "spread_home": proj["margin"],
            "home_win_chance": proj["win_probability"],
            "proj_home": proj["score_a"],
            "proj_away": proj["score_b"],
            "margin_low": proj["margin_low"],
            "margin_high": proj["margin_high"],
            "rating_basis": "season",
        })
    rows.sort(key=lambda g: (g["week"] if g["week"] is not None else 99, g["home"], g["away"]))
    return rows


def attach_outlook(teams: list[dict], games: list[dict]) -> None:
    """Fill schedule expected wins and the projected remaining record."""
    for team in teams:
        expected = 0.0
        remaining_expected = 0.0
        remaining = 0
        for game in games:
            if team["team"] == game["home"]:
                chance = game["home_win_chance"]
            elif team["team"] == game["away"]:
                chance = 1.0 - game["home_win_chance"]
            else:
                continue
            expected += chance
            if not game["played"]:
                remaining_expected += chance
                remaining += 1
        team["schedule_expected_wins"] = expected
        team["remaining_games"] = remaining
        team["projected_wins"] = team["wins"] + remaining_expected
        team["projected_losses"] = team["losses"] + (remaining - remaining_expected)


def opponent_strength(teams: list[dict], games: list[dict]) -> None:
    """Average final v2 of opponents already played. Unplayed games are not SOS."""
    ratings = {team["team"]: team["v2"] for team in teams}
    buckets = {team["team"]: [] for team in teams}
    for game in games:
        if not game["played"]:
            continue
        buckets[game["home"]].append(ratings[game["away"]])
        buckets[game["away"]].append(ratings[game["home"]])
    for team in teams:
        faced = buckets[team["team"]]
        team["sos"] = sum(faced) / len(faced) if faced else None
        team["sos_games"] = len(faced)
