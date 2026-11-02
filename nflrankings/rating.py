"""v2 rating: schedule-adjusted EPA margin. No I/O."""

from __future__ import annotations

import pandas as pd

ITERATIONS = 20


def raw_epa(plays: pd.DataFrame) -> pd.DataFrame:
    """Play-weighted raw EPA per team.

    ``plays`` needs columns ``posteam``, ``defteam`` and ``epa`` (non-null).
    Returns a frame indexed by team with ``off_epa``, ``def_epa``,
    ``off_plays`` and ``def_plays``.
    """
    off = plays.groupby("posteam")["epa"].agg(off_epa="mean", off_plays="size")
    dfn = plays.groupby("defteam")["epa"].agg(def_epa="mean", def_plays="size")
    return off.join(dfn, how="outer").fillna(0.0).sort_index()


def adjust(plays: pd.DataFrame, iterations: int = ITERATIONS) -> pd.DataFrame:
    """Opponent-adjust EPA and return one row per team.

    Columns: off_epa, def_epa, off_epa_adj, def_epa_adj, v2 (= adj_off - adj_def).
    Lower ``def_epa`` is a better defense; higher ``v2`` is a better team.
    """
    raw = raw_epa(plays)
    teams = list(raw.index)
    # Play counts for each (team, opponent) pairing, in both directions.
    pair = plays.groupby(["posteam", "defteam"]).size().unstack(fill_value=0)
    pair = pair.reindex(index=teams, columns=teams, fill_value=0).astype(float)
    off_w = pair.div(pair.sum(axis=1).replace(0, 1), axis=0)  # team (off) vs opp (def)
    pair_d = pair.T  # rows: team on defense, columns: opposing offense
    def_w = pair_d.div(pair_d.sum(axis=1).replace(0, 1), axis=0)

    raw_off, raw_def = raw["off_epa"], raw["def_epa"]
    adj_off, adj_def = raw_off.copy(), raw_def.copy()
    for _ in range(iterations):
        sos_off = off_w.dot(adj_def)
        sos_def = def_w.dot(adj_off)
        adj_off = raw_off - sos_off
        adj_def = raw_def - sos_def
        adj_off = adj_off - adj_off.mean() + raw_off.mean()
        adj_def = adj_def - adj_def.mean() + raw_def.mean()

    out = pd.DataFrame(
        {
            "off_epa": raw_off,
            "def_epa": raw_def,
            "off_epa_adj": adj_off,
            "def_epa_adj": adj_def,
        }
    )
    out["v2"] = out["off_epa_adj"] - out["def_epa_adj"]
    return out
