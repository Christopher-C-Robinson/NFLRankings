"""Lock the legacy formula against the 2022 workbook CSV exports."""

from pathlib import Path

import pandas as pd
import pytest

from nflrankings.legacy import (
    competition_ranks,
    legacy_function,
    legacy_net,
)

FIX = Path(__file__).parent / "fixtures" / "nfl2022"


def _load(name):
    return pd.read_csv(FIX / name).set_index("Tm")


def _side(prefix):
    total = _load(f"{prefix}_total.csv")
    drives = _load(f"{prefix}_drives.csv")
    conv = _load(f"{prefix}_conversions.csv")
    kick = _load(f"{prefix}_kicking.csv")
    out = {}
    for team in total.index:
        out[team] = legacy_function(
            pts_per_drive=drives.loc[team, "Pts"],
            fg_pct=kick.loc[team, "FG%"],
            xp_pct=kick.loc[team, "XP%"],
            yards_per_play=total.loc[team, "Y/P"],
            first_down_pct=total.loc[team, "1stD%"],
            third_down_rate=conv.loc[team, "3D%"],
            score_pct=drives.loc[team, "Sc%"],
            turnover_pct=drives.loc[team, "TO%"],
        )
    return out


@pytest.mark.parametrize("prefix", ["offense", "defense"])
def test_function_matches_workbook(prefix):
    total = _load(f"{prefix}_total.csv")
    got = _side(prefix)
    assert len(got) == 32
    for team, val in got.items():
        assert abs(val - total.loc[team, "FUNCTION"]) < 1e-6, team


def test_net_matches_overall_and_rank_order():
    overall = pd.read_csv(FIX / "overall_rankings.csv")
    off, deff = _side("offense"), _side("defense")
    assert len(overall) == 32
    nets = {}
    for _, row in overall.iterrows():
        net = legacy_net(off[row["Team"]], deff[row["Team"]])
        assert abs(net - row["FUNCTION"]) < 1e-6, row["Team"]
        nets[row["Team"]] = net
    order = sorted(nets, key=nets.get, reverse=True)
    expected = overall.sort_values("Overall Rank")["Team"].tolist()
    assert order == expected
    teams = list(nets)
    ranks = competition_ranks([nets[t] for t in teams])
    for t, r in zip(teams, ranks):
        assert r == int(overall.set_index("Team").loc[t, "Overall Rank"])


def test_competition_ranks_ties():
    assert competition_ranks([3, 2, 2, 1]) == [1, 2, 2, 4]
    assert competition_ranks([3, 2, 2, 1], higher_is_better=False) == [4, 2, 2, 1]
