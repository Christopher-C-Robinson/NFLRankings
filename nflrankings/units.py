"""Play and drive observations for the pregame screens.

Each frame has ``week``, ``posteam``, ``defteam``, and ``epa``. The ``epa``
column is the value to opponent-adjust, not necessarily nflverse EPA. Higher
is better for the offense. These rows are how the walk-forward screens measured
parts of the game that one scrimmage-EPA number does not separate. They are
not an input to the published spread unless a later screen promotes them.
See ``scripts/screen_advanced.py``, ``scripts/screen_aspects.py``, and the
methodology page.
"""

from __future__ import annotations

import pandas as pd

from .aggregate import regular_season, scrimmage_plays

# Kickoffs, punts, field goals, and extra points. Scrimmage EPA leaves these out.
SPECIAL_TEAMS = ("kickoff", "punt", "field_goal", "extra_point")
# A pass of this many yards, or a run of the rush threshold, counts as explosive.
EXPLOSIVE_PASS_YARDS = 20
EXPLOSIVE_RUSH_YARDS = 10


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["week", "posteam", "defteam", "epa"])


def _ready(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep rows that can enter the opponent adjustment."""
    if frame.empty:
        return _empty()
    out = frame.copy()
    out["week"] = pd.to_numeric(out["week"], errors="coerce")
    out["epa"] = pd.to_numeric(out["epa"], errors="coerce")
    keep = out["posteam"].notna() & out["defteam"].notna() & out["epa"].notna() & out["week"].notna()
    out = out.loc[keep, ["week", "posteam", "defteam", "epa"]]
    return out.reset_index(drop=True)


def special_teams_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Special-teams plays, with nflverse EPA as the value.

    Positive EPA is good for ``posteam``. Kickoff and punt rows use the team
    nflverse credits, which is the kicking team.
    """
    if "play_type" not in pbp.columns or "epa" not in pbp.columns:
        return _empty()
    df = regular_season(pbp)
    keep = df["play_type"].isin(SPECIAL_TEAMS)
    if "posteam" in df.columns:
        keep = keep & df["posteam"].notna()
    if "defteam" in df.columns:
        keep = keep & df["defteam"].notna()
    return _ready(df.loc[keep])


def drive_start_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per offensive drive. Value is yards from the offense's own goal.

    The drive starts at the first pass or run, after the kickoff that nflverse
    stores on the same drive. Yard line 100 is the offense's own goal, so the
    stored value is ``100 - yardline_100``. A higher number is a better start.
    """
    needed = {"game_id", "fixed_drive", "play_id", "play_type", "posteam", "defteam", "yardline_100", "week"}
    if not needed.issubset(pbp.columns):
        return _empty()
    df = regular_season(pbp)
    scr = df[df["play_type"].isin(["pass", "run"]) & df["posteam"].notna() & df["defteam"].notna() & df["fixed_drive"].notna()]
    if scr.empty:
        return _empty()
    scr = scr.sort_values(["game_id", "fixed_drive", "play_id"])
    first = scr.groupby(["game_id", "fixed_drive"], as_index=False).nth(0)
    yards = 100.0 - pd.to_numeric(first["yardline_100"], errors="coerce")
    return _ready(first.assign(epa=yards))


def success_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage plays whose value is nflverse ``success`` (1 or 0)."""
    if "success" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty or "success" not in plays.columns:
        return _empty()
    return _ready(plays.assign(epa=plays["success"]))


def explosive_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage plays: 1 for a 20-yard pass or a 10-yard run, otherwise 0."""
    if "yards_gained" not in pbp.columns or "play_type" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    yards = pd.to_numeric(plays["yards_gained"], errors="coerce")
    explosive = (plays["play_type"].eq("pass") & yards.ge(EXPLOSIVE_PASS_YARDS)) | (
        plays["play_type"].eq("run") & yards.ge(EXPLOSIVE_RUSH_YARDS)
    )
    return _ready(plays.assign(epa=explosive.astype(float)))


def scrimmage_epa_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Regular-season scrimmage EPA, the same plays the published rating uses."""
    if "epa" not in pbp.columns:
        return _empty()
    return _ready(scrimmage_plays(pbp))


def pass_epa_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Pass plays only, nflverse EPA."""
    if "epa" not in pbp.columns:
        return _empty()
    return _ready(scrimmage_plays(pbp, ("pass",)))


def rush_epa_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Run plays only, nflverse EPA. Kneels are not ``run`` rows."""
    if "epa" not in pbp.columns:
        return _empty()
    return _ready(scrimmage_plays(pbp, ("run",)))


def _down_epa(pbp: pd.DataFrame, downs: set[int]) -> pd.DataFrame:
    if "down" not in pbp.columns or "epa" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    down = pd.to_numeric(plays["down"], errors="coerce")
    return _ready(plays.loc[down.isin(downs)])


def early_down_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage EPA on first and second down."""
    return _down_epa(pbp, {1, 2})


def late_down_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage EPA on third and fourth down."""
    return _down_epa(pbp, {3, 4})


def redzone_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage EPA with the ball inside the opponent's 20.

    ``yardline_100`` is yards from the opponent's goal line.
    """
    if "yardline_100" not in pbp.columns or "epa" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    yards = pd.to_numeric(plays["yardline_100"], errors="coerce")
    return _ready(plays.loc[yards.le(20)])


def competitive_epa_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage EPA when pre-play win probability is between 10% and 90%.

    This drops garbage-time snaps. ``wp`` is the win probability before the
    play, so the filter uses that play's state and not the final score.
    """
    if "wp" not in pbp.columns or "epa" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    wp = pd.to_numeric(plays["wp"], errors="coerce")
    return _ready(plays.loc[wp.between(0.10, 0.90)])


def yards_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage yards gained. Higher is better for the offense."""
    if "yards_gained" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    return _ready(plays.assign(epa=pd.to_numeric(plays["yards_gained"], errors="coerce")))


def _flag(plays: pd.DataFrame, column: str) -> pd.Series:
    if column not in plays.columns:
        return pd.Series(False, index=plays.index)
    return pd.to_numeric(plays[column], errors="coerce").fillna(0).eq(1)


def turnover_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """1 on a scrimmage play with no interception and no lost fumble, else 0.

    Higher is better for the offense. A defense that takes the ball away shows
    up as a low value allowed, which is a better defense after adjustment.
    """
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    turnover = _flag(plays, "interception") | _flag(plays, "fumble_lost")
    return _ready(plays.assign(epa=(~turnover).astype(float)))


def _pass_plays(pbp: pd.DataFrame) -> pd.DataFrame:
    plays = scrimmage_plays(pbp, ("pass",))
    if plays.empty or "epa" not in plays.columns:
        return plays.iloc[0:0]
    return plays


def sack_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """1 on a pass play that is not a sack, else 0. Higher is better for the offense."""
    if "sack" not in pbp.columns:
        return _empty()
    plays = _pass_plays(pbp)
    if plays.empty:
        return _empty()
    return _ready(plays.assign(epa=(~_flag(plays, "sack")).astype(float)))


def pressure_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """1 on a pass play with no quarterback hit and no sack, else 0."""
    if "qb_hit" not in pbp.columns and "sack" not in pbp.columns:
        return _empty()
    plays = _pass_plays(pbp)
    if plays.empty:
        return _empty()
    pressure = _flag(plays, "qb_hit") | _flag(plays, "sack")
    return _ready(plays.assign(epa=(~pressure).astype(float)))


def penalty_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Penalty yards from the offense's side. A defensive penalty is positive.

    Plays with no penalty are 0. Yards charged to ``posteam`` are negative.
    """
    if "penalty_team" not in pbp.columns or "penalty_yards" not in pbp.columns:
        return _empty()
    plays = scrimmage_plays(pbp)
    if plays.empty:
        return _empty()
    yards = pd.to_numeric(plays["penalty_yards"], errors="coerce").fillna(0.0)
    charged = plays["penalty_team"]
    value = pd.Series(0.0, index=plays.index)
    value = value.mask(charged.eq(plays["posteam"]), -yards)
    value = value.mask(charged.eq(plays["defteam"]), yards)
    return _ready(plays.assign(epa=value))


def _drive_first(pbp: pd.DataFrame) -> pd.DataFrame:
    needed = {"game_id", "fixed_drive", "play_id", "play_type", "posteam", "defteam", "week"}
    if not needed.issubset(pbp.columns):
        return pd.DataFrame()
    df = regular_season(pbp)
    scr = df[df["play_type"].isin(["pass", "run"]) & df["posteam"].notna() & df["defteam"].notna() & df["fixed_drive"].notna()]
    if scr.empty:
        return pd.DataFrame()
    scr = scr.sort_values(["game_id", "fixed_drive", "play_id"])
    return scr.groupby(["game_id", "fixed_drive"], as_index=False).nth(0)


def drive_points_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """Points scored by the drive's offense, one row per drive.

    The end of the drive has to stay with the same offense. A drive that ends
    on the other team's play is left out rather than charged as zero or as
    the other team's points.
    """
    needed = {"posteam_score", "posteam_score_post"}
    if not needed.issubset(pbp.columns):
        return _empty()
    first = _drive_first(pbp)
    if first.empty:
        return _empty()
    df = regular_season(pbp)
    owned = df[df["fixed_drive"].notna() & df["posteam"].notna()].sort_values("play_id")
    last = owned.groupby(["game_id", "fixed_drive"], as_index=False).nth(-1)
    merged = first[["game_id", "fixed_drive", "week", "posteam", "defteam", "posteam_score"]].merge(
        last[["game_id", "fixed_drive", "posteam", "posteam_score_post"]].rename(
            columns={"posteam": "end_team", "posteam_score_post": "end_score"}
        ),
        on=["game_id", "fixed_drive"],
        how="left",
    )
    same = merged["end_team"].eq(merged["posteam"])
    points = (merged["end_score"] - merged["posteam_score"]).where(same)
    return _ready(merged.assign(epa=points))


def drive_score_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """1 when the drive ends in a touchdown or a field goal, else 0."""
    if "fixed_drive_result" not in pbp.columns:
        return _empty()
    first = _drive_first(pbp)
    if first.empty:
        return _empty()
    scored = first["fixed_drive_result"].isin(["Touchdown", "Field goal"])
    known = first["fixed_drive_result"].notna()
    return _ready(first.loc[known].assign(epa=scored.loc[known].astype(float)))


def drive_clean_observations(pbp: pd.DataFrame) -> pd.DataFrame:
    """1 when the drive result is not a turnover, else 0.

    Higher is better for the offense. ``Turnover on downs`` is a failed
    drive, not a giveaway, and stays at 1 here. Points per drive already
    charges the failed trip.
    """
    if "fixed_drive_result" not in pbp.columns:
        return _empty()
    first = _drive_first(pbp)
    if first.empty:
        return _empty()
    known = first["fixed_drive_result"].notna()
    clean = ~first["fixed_drive_result"].eq("Turnover")
    return _ready(first.loc[known].assign(epa=clean.loc[known].astype(float)))
