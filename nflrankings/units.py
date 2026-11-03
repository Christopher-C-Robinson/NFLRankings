"""Drive and special-teams observations for the pregame screen.

Each frame has ``week``, ``posteam``, ``defteam``, and ``epa``. The ``epa``
column is the value to opponent-adjust with ``rating.adjust``, not necessarily
nflverse EPA. Higher is better for the offense. These rows are how the
walk-forward screen measured rates that scrimmage EPA does not already use.
They are not an input to the published spread. See ``scripts/screen_advanced.py``
and the methodology page.
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
