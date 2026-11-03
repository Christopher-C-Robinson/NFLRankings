"""Download nflverse data, rate, and write JSON/CSV under docs/data."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import rating
from .aggregate import PBP_COLUMNS, epa_plays, regular_season
from .group_power import attach_group_power
from .schedule import (
    attach_outlook,
    attach_pregame,
    attach_wins_above_expected,
    league_ppg,
    opponent_strength,
    prior_ratings_from_teams,
    season_games,
    unit_ratings,
    weekly_v2,
)
from .weeks import describe_weeks
from .winprob import apply_win_chances, load_conversion

SOURCE = "nflverse via nfl_data_py (https://github.com/nflverse)"
# The public site starts at 2025. Earlier seasons still build, and they can be
# written to a directory other than docs/data, but they are not published.
PUBLIC_SEASON_MIN = 2025
SCHEDULE_FALLBACK = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "data"

# Historical / alternate abbreviations -> abbreviations used in recent pbp.
ABBR_FIX = {"LAR": "LA", "STL": "LA", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "JAC": "JAX"}
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_HTTPS = re.compile(r"^https://[^\s\\]+$")

CSV_COLUMNS = [
    "win_chance_rank", "team", "name", "conference", "division",
    "wins", "losses", "ties", "point_diff",
    "win_chance", "mean_margin", "expected_wins", "opponents",
    "v2", "v2_rank", "off_epa", "def_epa", "off_epa_adj", "def_epa_adj",
    "color", "color2", "logo",
    "points_for", "points_against",
    "off_pass_epa_adj", "def_pass_epa_adj", "off_rush_epa_adj", "def_rush_epa_adj",
    "schedule_expected_wins", "projected_wins", "projected_losses", "sos",
    "pregame_expected_wins", "wins_above_expected",
    "hierarchy_power", "unpooled_power", "division_power", "conference_power",
]


def align_abbr(abbr, known: set[str] | None = None):
    """Map a schedule abbreviation onto the pbp rating index.

    With no ``known`` set, apply the historical rename table only.
    """
    if abbr is None or (isinstance(abbr, float) and math.isnan(abbr)):
        return None
    raw = str(abbr)
    if known is None:
        return ABBR_FIX.get(raw, raw)
    if raw in known:
        return raw
    fixed = ABBR_FIX.get(raw)
    if fixed in known:
        return fixed
    for src, dst in ABBR_FIX.items():
        if dst == raw and src in known:
            return src
    return None


def norm_abbr(abbr):
    """Normalize a team abbreviation to the recent pbp form."""
    return align_abbr(abbr)


def download_pbp(season: int) -> pd.DataFrame:
    """Download one season of play-by-play via nfl_data_py (empty if unavailable)."""
    import nfl_data_py as nfl

    for cols in (PBP_COLUMNS, None):
        try:
            kwargs = {"columns": cols} if cols else {}
            return nfl.import_pbp_data([season], include_participation=False, downcast=True, cache=False, **kwargs)
        except Exception as exc:  # noqa: BLE001 - missing column or missing season
            print(f"pbp import ({'filtered' if cols else 'all columns'}) failed for {season}: {exc}")
    return pd.DataFrame()


def download_schedule(season: int) -> pd.DataFrame:
    """Download one season's schedule, falling back to the nflverse release CSV."""
    import nfl_data_py as nfl

    try:
        sched = nfl.import_schedules([season])
    except Exception as exc:  # noqa: BLE001
        print(f"import_schedules failed ({exc}); using nflverse release fallback")
        sched = pd.read_csv(SCHEDULE_FALLBACK)
        sched = sched[sched["season"] == season]
    return sched


def download_teams() -> pd.DataFrame:
    """Download team metadata from nfl_data_py."""
    import nfl_data_py as nfl

    return nfl.import_team_desc()


def records(sched: pd.DataFrame, known: set[str]) -> pd.DataFrame:
    """Wins, losses, ties and point differential from played REG games."""
    games = sched[(sched["game_type"] == "REG") & sched["home_score"].notna() & sched["away_score"].notna()]
    rows = {}
    for record in games.itertuples(index=False):
        sides = (
            (align_abbr(record.home_team, known), record.home_score, record.away_score),
            (align_abbr(record.away_team, known), record.away_score, record.home_score),
        )
        if sides[0][0] is None or sides[1][0] is None:
            continue
        for team, points_for, points_against in sides:
            bucket = rows.setdefault(team, {
                "wins": 0, "losses": 0, "ties": 0, "point_diff": 0, "points_for": 0, "points_against": 0,
            })
            bucket["wins"] += int(points_for > points_against)
            bucket["losses"] += int(points_for < points_against)
            bucket["ties"] += int(points_for == points_against)
            bucket["point_diff"] += int(points_for - points_against)
            bucket["points_for"] += int(points_for)
            bucket["points_against"] += int(points_against)
    return pd.DataFrame.from_dict(rows, orient="index")


def _clean(value, digits=6):
    """Round a float, raising if it is not finite."""
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite value in output")
    return round(value, digits)


def _css_color(value) -> str:
    """Keep a #RRGGBB color; drop anything else so it cannot break CSS."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text.upper() if _HEX.match(text) else ""


def _https_url(value) -> str:
    """Keep an https URL; drop other schemes."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if _HTTPS.match(text) else ""


def _logo(meta) -> str:
    """Prefer the nflverse ESPN logo, then the Wikipedia logo."""
    if meta is None:
        return ""
    return _https_url(meta.get("team_logo_espn")) or _https_url(meta.get("team_logo_wikipedia"))


def _cell(meta, column: str) -> str:
    if meta is None or column not in meta.index:
        return ""
    value = meta[column]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


def ranking_block(params: dict) -> dict:
    """Season-level conversion facts copied onto every payload."""
    keys = (
        "method", "ranking", "fit_seasons_first", "fit_seasons_last", "fit_games", "fit_ties",
        "neutral_games", "epa_to_points", "home_field_points", "win_prob_scale",
        "margin_r2", "margin_residual_sd", "home_win_rate", "mean_predicted_home_win",
    )
    return {key: params[key] for key in keys if key in params}


def build_teams(pbp: pd.DataFrame, sched: pd.DataFrame, team_desc: pd.DataFrame, params: dict | None = None) -> list[dict]:
    """Combine v2 EPA, neutral win chance, metadata and records."""
    params = load_conversion() if params is None else params
    adjusted = rating.adjust(epa_plays(pbp))
    known = set(adjusted.index)
    rec = records(sched, known)
    desc = team_desc.copy()
    desc["abbr"] = desc["team_abbr"].map(lambda abbr: align_abbr(abbr, known) or norm_abbr(abbr))
    desc = desc.drop_duplicates("abbr", keep="first").set_index("abbr")

    rows = []
    for team in sorted(known):
        meta = desc.loc[team] if team in desc.index else None
        record = rec.loc[team] if team in rec.index else {
            "wins": 0, "losses": 0, "ties": 0, "point_diff": 0, "points_for": 0, "points_against": 0,
        }
        rows.append({
            "team": team,
            "name": _cell(meta, "team_name") or team,
            "conference": _cell(meta, "team_conf"),
            "division": _cell(meta, "team_division"),
            "wins": int(record["wins"]),
            "losses": int(record["losses"]),
            "ties": int(record["ties"]),
            "point_diff": int(record["point_diff"]),
            "points_for": int(record["points_for"]),
            "points_against": int(record["points_against"]),
            "v2": _clean(adjusted.loc[team, "v2"]),
            "off_epa": _clean(adjusted.loc[team, "off_epa"]),
            "def_epa": _clean(adjusted.loc[team, "def_epa"]),
            "off_epa_adj": _clean(adjusted.loc[team, "off_epa_adj"]),
            "def_epa_adj": _clean(adjusted.loc[team, "def_epa_adj"]),
            "color": _css_color(meta["team_color"]) if meta is not None and "team_color" in meta.index else "",
            "color2": _css_color(meta["team_color2"]) if meta is not None and "team_color2" in meta.index else "",
            "logo": _logo(meta),
        })
    # Rank from the rounded EPA values so a reader of the file gets the same chances.
    apply_win_chances(rows, params)
    units = unit_ratings(pbp, [row["team"] for row in rows])
    weeks = weekly_v2(pbp, [row["team"] for row in rows])
    for row in rows:
        row["win_chance"] = _clean(row["win_chance"])
        row["mean_margin"] = _clean(row["mean_margin"], 4)
        row["expected_wins"] = _clean(row["expected_wins"], 4)
        for key, value in units[row["team"]].items():
            row[key] = value if isinstance(value, int) or value is None else _clean(value)
        row["weeks"] = [{"week": point["week"], "v2": _clean(point["v2"])} for point in weeks[row["team"]]]
    return rows


def _round_game(game: dict) -> dict:
    for key, digits in (
        ("spread_home", 4), ("home_win_chance", 6), ("proj_home", 4), ("proj_away", 4),
        ("margin_low", 4), ("margin_high", 4), ("pregame_spread_home", 4),
        ("pregame_home_win_chance", 6), ("pregame_proj_home", 4), ("pregame_proj_away", 4),
        ("pregame_margin_low", 4), ("pregame_margin_high", 4),
    ):
        if key in game and game[key] is not None:
            game[key] = _clean(game[key], digits)
    return game


def enrich_games(
    teams: list[dict],
    sched: pd.DataFrame,
    params: dict,
    known: set[str],
    pbp: pd.DataFrame | None = None,
    prior_v2: dict[str, float] | None = None,
) -> tuple[list[dict], float]:
    """Add schedule projections. Returns (games, league points per team-game)."""
    ppg = league_ppg(pd.DataFrame(teams).set_index("team")) if teams else 0.0
    fitted = dict(params)
    fitted["_league_ppg"] = ppg
    games = season_games(sched, teams, fitted, known, align_abbr)
    if pbp is not None:
        attach_pregame(teams, games, pbp, params, prior_v2=prior_v2)
        attach_wins_above_expected(teams, games)
    games = [_round_game(game) for game in games]
    attach_outlook(teams, games)
    opponent_strength(teams, games)
    for team in teams:
        team["schedule_expected_wins"] = _clean(team["schedule_expected_wins"], 4)
        team["projected_wins"] = _clean(team["projected_wins"], 4)
        team["projected_losses"] = _clean(team["projected_losses"], 4)
        team["sos"] = None if team["sos"] is None else _clean(team["sos"])
        if "wins_above_expected" in team:
            team["pregame_expected_wins"] = _clean(team["pregame_expected_wins"], 4)
            team["wins_above_expected"] = _clean(team["wins_above_expected"], 4)
    return games, _clean(ppg) if ppg else 0.0


def _publishes(season: int, out_dir: Path) -> bool:
    """True when this season should be written for the site or a research directory.

    ``docs/data`` only receives seasons from ``PUBLIC_SEASON_MIN`` forward.
    Another output directory can still hold an older backfill.
    """
    if int(season) >= PUBLIC_SEASON_MIN:
        return True
    return out_dir.resolve() != DEFAULT_OUT.resolve()


def ensure_prior_season(season: int, out_dir: Path, params: dict) -> dict[str, float]:
    """Load season-1 end ratings, building that season first when the file is missing.

    The nested build does not itself fetch a prior, so a 2026 refresh materializes
    2025 and stops there. A prior older than the public window is kept in memory
    instead of being written under ``docs/data``. An empty result means there is
    nothing to blend.
    """
    prior_year = season - 1
    path = out_dir / f"{prior_year}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return prior_ratings_from_teams(data.get("teams", []))
    payload = build_season(prior_year, params, out_dir=out_dir, fetch_prior=False)
    if payload is None:
        print(f"no prior season {prior_year}")
        return {}
    if _publishes(prior_year, out_dir):
        write_season(payload, out_dir)
        print(f"materialized prior season {prior_year}: {len(payload['teams'])} teams")
    else:
        print(f"prior season {prior_year} used in memory and not published")
    return prior_ratings_from_teams(payload.get("teams", []))


def build_season(season: int, params: dict | None = None, *, out_dir: Path | None = None, fetch_prior: bool = True):
    """Build one season; return a payload dict, or None if there are no REG plays."""
    params = load_conversion() if params is None else params
    pbp = download_pbp(season)
    if pbp.empty:
        return None
    reg = regular_season(pbp)
    if reg.empty or not reg["play_type"].isin(["pass", "run"]).any():
        return None
    sched = download_schedule(season)
    teams = build_teams(pbp, sched, download_teams(), params)
    known = {team["team"] for team in teams}
    prior = ensure_prior_season(season, out_dir or DEFAULT_OUT, params) if fetch_prior else {}
    games, ppg = enrich_games(teams, sched, params, known, pbp, prior or None)
    return _payload(season, teams, reg, sched, params, games, ppg)


def _payload(season, teams, reg, sched, params, games=None, league_points=None) -> dict:
    weeks = pd.to_numeric(reg["week"], errors="coerce").dropna()
    played = sched[(sched["game_type"] == "REG") & sched["home_score"].notna()]
    week_max = int(weeks.max())
    catalog = describe_weeks(games or [], week_max)
    home_field = float(params.get("home_field_points", 0.0))
    return {
        "season": season,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "week_min": int(weeks.min()),
        "week_max": week_max,
        "games_played": int(len(played)),
        "league_ppg": league_points if league_points is not None else 0.0,
        "rating_basis": "season",
        "ranking": ranking_block(params),
        "week_calendar": catalog["calendar"],
        "current_week": catalog["current_week"],
        "current_week_reason": catalog["current_week_reason"],
        "weeks": catalog["weeks"],
        "group_power": attach_group_power(teams, games or [], home_field),
        "teams": teams,
        "games": games or [],
    }


def write_season(payload: dict, out_dir: Path) -> bool:
    """Write {season}.json and {season}.csv and refresh index.json.

    Returns False when the season is withheld from the public site. The payload
    is still available to the caller, so an older season can be backfilled into
    a different directory.
    """
    season = int(payload["season"])
    if not _publishes(season, out_dir):
        print(f"season {season} was not published; public seasons start at {PUBLIC_SEASON_MIN}")
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{season}.json").write_text(json.dumps(payload, indent=1) + "\n")
    frame = pd.DataFrame(payload["teams"])
    frame = frame.reindex(columns=[c for c in CSV_COLUMNS if c in frame.columns])
    frame.to_csv(out_dir / f"{season}.csv", index=False)
    idx_path = out_dir / "index.json"
    seasons = set()
    if idx_path.exists():
        seasons = set(json.loads(idx_path.read_text()).get("seasons", []))
    if out_dir.resolve() == DEFAULT_OUT.resolve():
        seasons = {int(year) for year in seasons if int(year) >= PUBLIC_SEASON_MIN}
    seasons.add(season)
    seasons = sorted(seasons, reverse=True)
    index = {
        "seasons": seasons,
        "default_season": seasons[0],
        "generated_at": payload["generated_at"],
        "source": SOURCE,
        "ranking": payload.get("ranking", {}).get("ranking", "neutral-round-robin"),
    }
    idx_path.write_text(json.dumps(index, indent=1) + "\n")
    return True


def run(season: str, out_dir: Path = DEFAULT_OUT) -> int:
    """Build ``season`` (an int string or 'latest'); return the season written."""
    params = load_conversion()
    if season == "latest":
        year = datetime.now(timezone.utc).year
        candidates = [year, year - 1]
    else:
        candidates = [int(season)]
    for candidate in candidates:
        payload = build_season(candidate, params, out_dir=out_dir)
        if payload is None:
            print(f"no regular-season plays for {candidate}")
            continue
        if write_season(payload, out_dir):
            print(f"wrote season {candidate}: {len(payload['teams'])} teams")
        return candidate
    raise SystemExit(f"no data available for {season}")
