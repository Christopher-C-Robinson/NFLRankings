"""Play-by-play dataframe -> per-team legacy component dicts. No network.

Approximations (see README / methodology.html):

* Regular season only; scrimmage plays are ``pass``/``run`` rows that are not
  ``no_play``, have a ``posteam`` and are not two-point attempts.
* A drive is ``(game_id, posteam, fixed_drive)``; kickoff rows are ignored.
* ``drive_ended_with_score`` also flags defensive scores (pick-sixes,
  safeties), so it only counts when ``fixed_drive_result`` is a touchdown or
  field goal for the offense.
* Points per drive are summed from offensive TD/FG/XP/2PT events.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SCRIMMAGE = ("pass", "run")
PBP_COLUMNS = [
    "game_id", "season", "season_type", "week", "posteam", "defteam", "play_type",
    "yards_gained", "epa", "first_down", "first_down_pass",
    "first_down_rush", "first_down_penalty", "third_down_converted",
    "third_down_failed", "field_goal_attempt", "field_goal_result",
    "extra_point_attempt", "extra_point_result", "two_point_attempt",
    "two_point_conv_result", "fixed_drive", "fixed_drive_result",
    "drive_ended_with_score", "touchdown", "td_team", "interception", "fumble_lost",
]
COMPONENT_KEYS = [
    "pts_per_drive", "fg_pct", "xp_pct", "yards_per_play", "first_down_pct",
    "third_down_rate", "score_pct", "turnover_pct", "plays", "drives",
]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Numeric column with NaN -> 0; all zeros if the column is missing."""
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _str(df: pd.DataFrame, col: str) -> pd.Series:
    """String column with NaN -> ''; empty strings if the column is missing."""
    if col not in df.columns:
        return pd.Series("", index=df.index)
    return df[col].fillna("").astype(str)


def regular_season(pbp: pd.DataFrame) -> pd.DataFrame:
    """Return only regular-season rows (``season_type == 'REG'``)."""
    if "season_type" not in pbp.columns:
        return pbp
    return pbp[pbp["season_type"] == "REG"]


def scrimmage_plays(pbp: pd.DataFrame) -> pd.DataFrame:
    """Regular-season scrimmage plays with a posteam and defteam."""
    df = regular_season(pbp)
    keep = (
        _str(df, "play_type").isin(SCRIMMAGE)
        & (_num(df, "no_play") != 1)
        & (_num(df, "two_point_attempt") != 1)
        & df["posteam"].notna()
        & df["defteam"].notna()
    )
    return df[keep]


def epa_plays(pbp: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage plays with non-null EPA: columns posteam, defteam, epa."""
    s = scrimmage_plays(pbp)
    s = s[s["epa"].notna()]
    return s[["posteam", "defteam", "epa"]].astype({"epa": float})


def _first_downs(plays: pd.DataFrame) -> pd.Series:
    """First downs per play row, falling back to ``first_down`` if needed."""
    parts = ["first_down_pass", "first_down_rush", "first_down_penalty"]
    if all(c in plays.columns for c in parts):
        return sum(_num(plays, c) for c in parts)
    return _num(plays, "first_down")


def drive_table(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per drive with offensive points, scored and turnover flags."""
    df = regular_season(pbp)
    df = df[df["posteam"].notna() & df["defteam"].notna() & df["fixed_drive"].notna()]
    df = df[_str(df, "play_type") != "kickoff"]
    live = _num(df, "no_play") != 1
    scrim = _str(df, "play_type").isin(SCRIMMAGE)
    two = _num(df, "two_point_attempt") == 1
    off_td = (
        live & scrim & ~two & (_num(df, "touchdown") == 1)
        & (_str(df, "td_team") == df["posteam"])
    )
    fg_made = live & (_num(df, "field_goal_attempt") == 1) & (_str(df, "field_goal_result") == "made")
    xp_made = live & (_num(df, "extra_point_attempt") == 1) & (_str(df, "extra_point_result") == "good")
    two_made = live & two & (_str(df, "two_point_conv_result") == "success")
    flagged = (
        live
        & (_num(df, "drive_ended_with_score") == 1)
        & _str(df, "fixed_drive_result").isin(["Touchdown", "Field goal"])
    )
    turnover = live & scrim & ((_num(df, "interception") == 1) | (_num(df, "fumble_lost") == 1))
    work = pd.DataFrame(
        {
            "game_id": df["game_id"],
            "posteam": df["posteam"],
            "defteam": df["defteam"],
            "fixed_drive": df["fixed_drive"],
            "points": 6 * off_td + 3 * fg_made + xp_made + 2 * two_made,
            "scored": off_td | fg_made | flagged,
            "turnover": turnover,
        }
    )
    return work.groupby(["game_id", "posteam", "fixed_drive"], as_index=False).agg(
        defteam=("defteam", "first"),
        points=("points", "sum"),
        scored=("scored", "max"),
        turnover=("turnover", "max"),
    )


def kicking_table(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per FG/XP attempt with posteam, defteam and a made flag."""
    df = regular_season(pbp)
    df = df[df["posteam"].notna() & df["defteam"].notna() & (_num(df, "no_play") != 1)]
    fg = _num(df, "field_goal_attempt") == 1
    xp = _num(df, "extra_point_attempt") == 1
    df = df[fg | xp]
    fg, xp = fg[df.index], xp[df.index]
    made = (fg & (_str(df, "field_goal_result") == "made")) | (xp & (_str(df, "extra_point_result") == "good"))
    return pd.DataFrame(
        {"posteam": df["posteam"], "defteam": df["defteam"], "kind": np.where(fg, "fg", "xp"), "made": made}
    )


def _ratio(num, den, scale: float = 1.0):
    """num/den * scale as a Series, 0 where den is 0."""
    den = den.replace(0, np.nan)
    return (num / den * scale).fillna(0.0)


def _side(plays, drives, kicks, key: str) -> pd.DataFrame:
    """Component frame indexed by team, grouping every table on ``key``."""
    p = plays.assign(fd=_first_downs(plays), yds=_num(plays, "yards_gained"),
                     conv=_num(plays, "third_down_converted"), fail=_num(plays, "third_down_failed"))
    pg = p.groupby(key).agg(plays=("yds", "size"), yds=("yds", "sum"), fd=("fd", "sum"),
                            conv=("conv", "sum"), fail=("fail", "sum"))
    dg = drives.groupby(key).agg(drives=("points", "size"), points=("points", "sum"),
                                 scored=("scored", "sum"), turnover=("turnover", "sum"))
    kg = kicks.groupby([key, "kind"])["made"].agg(["sum", "size"]).unstack("kind", fill_value=0)
    out = pg.join(dg, how="outer").fillna(0.0)
    for kind in ("fg", "xp"):
        made = kg[("sum", kind)] if ("sum", kind) in kg.columns else pd.Series(0, index=out.index)
        att = kg[("size", kind)] if ("size", kind) in kg.columns else pd.Series(0, index=out.index)
        out[kind + "_made"] = made.reindex(out.index).fillna(0)
        out[kind + "_att"] = att.reindex(out.index).fillna(0)
    res = pd.DataFrame(index=out.index)
    res["pts_per_drive"] = _ratio(out["points"], out["drives"])
    res["fg_pct"] = _ratio(out["fg_made"], out["fg_att"])
    res["xp_pct"] = _ratio(out["xp_made"], out["xp_att"])
    res["yards_per_play"] = _ratio(out["yds"], out["plays"])
    res["first_down_pct"] = _ratio(out["fd"], out["plays"], 100.0)
    res["third_down_rate"] = _ratio(out["conv"], out["conv"] + out["fail"])
    res["score_pct"] = _ratio(out["scored"], out["drives"], 100.0)
    res["turnover_pct"] = _ratio(out["turnover"], out["drives"], 100.0)
    res["plays"] = out["plays"].astype(int)
    res["drives"] = out["drives"].astype(int)
    return res[COMPONENT_KEYS]


def team_components(pbp: pd.DataFrame) -> dict:
    """Per-team legacy inputs: ``{team: {"offense": {...}, "defense": {...}}}``.

    Defense values are the same stats over plays/drives where the team is the
    defense (what opponents did against it).
    """
    plays = scrimmage_plays(pbp)
    drives = drive_table(pbp)
    kicks = kicking_table(pbp)
    off = _side(plays, drives, kicks, "posteam")
    dfn = _side(plays, drives, kicks, "defteam")
    result = {}
    for team in sorted(set(off.index) | set(dfn.index)):
        result[team] = {
            side: {k: (float(frame.loc[team, k]) if team in frame.index else 0.0) for k in COMPONENT_KEYS}
            for side, frame in (("offense", off), ("defense", dfn))
        }
        for side in result[team].values():
            side["plays"] = int(side["plays"])
            side["drives"] = int(side["drives"])
    return result
