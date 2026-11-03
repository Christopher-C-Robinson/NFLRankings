"""Schedule projections and week-by-week EPA from plays already in memory."""

from __future__ import annotations

import pandas as pd

from .aggregate import rated_plays
from .rating import adjust
from .weeks import parse_gameday
from .winprob import project_game, shrink_rate

# k = 14 team-games, the middle of the 12–16 band. Selected on 2025 pregame
# results with 2024 as the prior, among k in {12, 14, 16} and shrink strengths
# in {8, 14, 20, 28}. 2026 was not used to pick it. A wider later grid,
# k in {0, 4, 8, 12, 14, 16, 20, 28, 40}, still gives 14 the most pooled
# 2018–2024 winners. k = 8 is higher only on 2025 and 2026, and lower before
# that, so it is not a replacement. One game a week means the live rating is
# still the smaller part after four games (4/18) and matches the prior only
# after 14 games.
BLEND_PRIOR_GAMES = 14
# A 17-game final rating keeps 17/45 of its gap to the league. The same 2025
# grid preferred this over a milder shrink: half-strength priors still swung
# too many early picks.
PRIOR_SHRINK_GAMES = 28
LEAGUE_V2 = 0.0

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


def kickoff_date(record) -> str | None:
    """ISO kickoff date from a schedule row, when the file has one.

    nflverse publishes ``gameday`` as the local calendar date. A missing
    column or a blank cell leaves the game on its integer week only.
    """
    for name in ("gameday", "game_date"):
        day = parse_gameday(getattr(record, name, None))
        if day is not None:
            return day.isoformat()
    return None


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
        row = {
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
        }
        day = kickoff_date(record)
        if day:
            row["gameday"] = day
        rows.append(row)
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


def shrink_prior_v2(prior_v2: float, games: int, shrink_games: int = PRIOR_SHRINK_GAMES) -> float:
    """Pull one team's previous-season v2 toward the league average.

    ``games`` is how many games that rating summarizes. Zero games stays at
    the league. The league v2 is 0 because the margin is already centered.
    """
    return shrink_rate(float(prior_v2), int(games), LEAGUE_V2, int(shrink_games))


def blend_v2(live_v2: float, prior_v2_shrunk: float, games_played: int, k: int = BLEND_PRIOR_GAMES) -> float:
    """Bayesian mix of the current rating and a shrunk prior.

    ``w = n / (n + k)`` with ``n`` games played so far. ``k`` of 0 uses the
    live rating only. This is not a hard cutoff: the prior fades as games arrive.
    """
    n = int(games_played)
    strength = int(k)
    if n < 0 or strength < 0:
        raise ValueError("game counts must be non-negative")
    if strength == 0:
        return float(live_v2)
    weight = n / (n + strength)
    return weight * float(live_v2) + (1.0 - weight) * float(prior_v2_shrunk)


def prior_ratings_from_teams(teams: list[dict]) -> dict[str, float]:
    """Shrunk end-of-season v2 keyed by abbreviation."""
    ratings = {}
    for team in teams:
        games = int(team.get("wins", 0)) + int(team.get("losses", 0)) + int(team.get("ties", 0))
        ratings[str(team["team"])] = shrink_prior_v2(float(team["v2"]), games)
    return ratings


def attach_pregame(
    teams: list[dict],
    games: list[dict],
    pbp: pd.DataFrame,
    params: dict,
    cold_ppg: float = 22.0,
    prior_v2: dict[str, float] | None = None,
) -> None:
    """Fill frozen pregame projections from plays strictly before each week.

    With no prior, week 1 has no plays yet, so every team is at the league
    rating and only home field moves the spread. When ``prior_v2`` has shrunk
    previous-season ratings, a thin sample is blended toward that prior:
    ``w * live + (1 - w) * prior`` with ``w = games / (games + 14)``. Scoring
    rates still use points from earlier weeks only, shrunk toward the league
    rate of those earlier games.

    Drive starts, special-teams EPA, success rate, explosiveness, and the
    wider aspect ridge in ``scripts/screen_aspects.py`` were measured on
    earlier seasons. They are not added here. On 2024 and 2025 none of those
    screens beat this scrimmage-EPA spread on both seasons.
    """
    ids = [team["team"] for team in teams]
    plays = rated_plays(pbp)
    if "week" in plays.columns:
        plays = plays.copy()
        plays["week"] = pd.to_numeric(plays["week"], errors="coerce")
    by_week: dict[int, list[dict]] = {}
    for game in games:
        if game["week"] is None:
            continue
        by_week.setdefault(int(game["week"]), []).append(game)
    points_for = {team: 0 for team in ids}
    points_against = {team: 0 for team in ids}
    played_games = {team: 0 for team in ids}
    for week in sorted(by_week):
        prior = plays[plays["week"] < week] if "week" in plays.columns else plays.iloc[0:0]
        if prior.empty or prior["posteam"].nunique() < 2 or prior["defteam"].nunique() < 2:
            ratings = {team: 0.0 for team in ids}
        else:
            rated = adjust(prior[["posteam", "defteam", "epa"]]).reindex(ids).fillna(0.0)
            ratings = {team: float(rated.loc[team, "v2"]) for team in ids}
        if prior_v2:
            for team in ids:
                ratings[team] = blend_v2(
                    ratings[team],
                    float(prior_v2.get(team, LEAGUE_V2)),
                    played_games[team],
                )
        seen = sum(played_games.values())
        league = (sum(points_for.values()) / seen) if seen else float(cold_ppg)

        def rate(team: str) -> dict:
            games_played = played_games[team]
            return {
                "points_for": (points_for[team] / games_played) if games_played else 0.0,
                "points_against": (points_against[team] / games_played) if games_played else 0.0,
                "games": games_played,
            }

        for game in by_week[week]:
            venue = "neutral" if game["neutral"] else "a_home"
            proj = project_game(
                ratings[game["home"]], ratings[game["away"]], params, venue,
                rate(game["home"]), rate(game["away"]), league,
            )
            game["pregame_spread_home"] = proj["margin"]
            game["pregame_home_win_chance"] = proj["win_probability"]
            game["pregame_proj_home"] = proj["score_a"]
            game["pregame_proj_away"] = proj["score_b"]
            game["pregame_margin_low"] = proj["margin_low"]
            game["pregame_margin_high"] = proj["margin_high"]
        for game in by_week[week]:
            if not game["played"]:
                continue
            points_for[game["home"]] += int(game["home_score"])
            points_against[game["home"]] += int(game["away_score"])
            points_for[game["away"]] += int(game["away_score"])
            points_against[game["away"]] += int(game["home_score"])
            played_games[game["home"]] += 1
            played_games[game["away"]] += 1


def attach_wins_above_expected(teams: list[dict], games: list[dict]) -> None:
    """Wins minus the sum of frozen pregame win chances on played games."""
    expected = {team["team"]: 0.0 for team in teams}
    for game in games:
        if not game["played"] or "pregame_home_win_chance" not in game:
            continue
        expected[game["home"]] += game["pregame_home_win_chance"]
        expected[game["away"]] += 1.0 - game["pregame_home_win_chance"]
    for team in teams:
        team["pregame_expected_wins"] = expected[team["team"]]
        team["wins_above_expected"] = team["wins"] - expected[team["team"]]


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
