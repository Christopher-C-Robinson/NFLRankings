"""Regular-season scrimmage plays for the EPA rating. No network.

Scrimmage plays are ``pass`` / ``run`` rows that are not two-point attempts,
have both teams, and are not marked ``no_play`` when that column exists.
nflverse's current play-by-play file has no ``no_play`` column; penalty-only
rows use a different ``play_type`` and already drop out.
"""

from __future__ import annotations

import pandas as pd

SCRIMMAGE = ("pass", "run")
PBP_COLUMNS = [
    "game_id",
    "season_type",
    "week",
    "posteam",
    "defteam",
    "play_type",
    "epa",
    "two_point_attempt",
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


def scrimmage_plays(pbp: pd.DataFrame, kinds: tuple[str, ...] = SCRIMMAGE) -> pd.DataFrame:
    """Regular-season scrimmage plays with a posteam and defteam."""
    df = regular_season(pbp)
    keep = (
        _str(df, "play_type").isin(kinds)
        & (_num(df, "no_play") != 1)
        & (_num(df, "two_point_attempt") != 1)
        & df["posteam"].notna()
        & df["defteam"].notna()
    )
    return df[keep]


def rated_plays(pbp: pd.DataFrame, kinds: tuple[str, ...] = SCRIMMAGE) -> pd.DataFrame:
    """Scrimmage plays with non-null EPA, keeping week and play type when present."""
    plays = scrimmage_plays(pbp, kinds)
    plays = plays[plays["epa"].notna()].copy()
    plays["epa"] = plays["epa"].astype(float)
    columns = ["posteam", "defteam", "epa"]
    if "week" in plays.columns:
        columns.append("week")
    if "play_type" in plays.columns:
        columns.append("play_type")
    return plays[columns]


def epa_plays(pbp: pd.DataFrame, kinds: tuple[str, ...] = SCRIMMAGE) -> pd.DataFrame:
    """Scrimmage plays with non-null EPA: columns posteam, defteam, epa."""
    return rated_plays(pbp, kinds)[["posteam", "defteam", "epa"]]
