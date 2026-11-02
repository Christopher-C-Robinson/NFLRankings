"""Aggregation tests on a small in-memory pbp frame (no network)."""

import numpy as np
import pandas as pd
import pytest

from nflrankings.aggregate import drive_table, epa_plays, team_components


def _row(**kw):
    base = dict(game_id="g1", season_type="REG", week=1, posteam=None, defteam=None, play_type=None,
                yards_gained=0.0, epa=0.0, first_down_pass=0, first_down_rush=0, first_down_penalty=0,
                third_down_converted=0, third_down_failed=0, field_goal_attempt=0, field_goal_result=None,
                extra_point_attempt=0, extra_point_result=None, two_point_attempt=0,
                two_point_conv_result=None, fixed_drive=1, fixed_drive_result=None,
                drive_ended_with_score=0, touchdown=0, td_team=None, interception=0, fumble_lost=0)
    base.update(kw)
    return base


def _pbp():
    A = dict(posteam="AAA", defteam="BBB")
    B = dict(posteam="BBB", defteam="AAA")
    rows = [
        # Drive 1 (AAA): run, 3rd-down pass conversion first down, TD pass, XP good -> 7 points.
        _row(**A, play_type="run", yards_gained=4, epa=0.1, third_down_failed=0),
        _row(**A, play_type="pass", yards_gained=10, epa=0.5, first_down_pass=1, third_down_converted=1),
        _row(**A, play_type="pass", yards_gained=20, epa=2.0, touchdown=1, td_team="AAA",
             fixed_drive_result="Touchdown", drive_ended_with_score=1),
        _row(**A, play_type="extra_point", extra_point_attempt=1, extra_point_result="good",
             fixed_drive_result="Touchdown", drive_ended_with_score=1),
        # kickoff after the score is ignored for drives
        _row(**A, play_type="kickoff", fixed_drive=1),
        # Drive 2 (BBB): interception returned for a TD by AAA (defensive score).
        _row(**B, play_type="pass", yards_gained=0, epa=-7.0, interception=1, fixed_drive=2,
             fixed_drive_result="Opp touchdown", drive_ended_with_score=1, touchdown=1, td_team="AAA"),
        # Drive 3 (AAA): 3rd-down failure, then missed FG, with a no_play penalty row that must be ignored.
        _row(**A, play_type="run", yards_gained=2, epa=-0.2, third_down_failed=1, fixed_drive=3),
        _row(**A, play_type="no_play", yards_gained=0, epa=0.0, fixed_drive=3),
        _row(**A, play_type="field_goal", field_goal_attempt=1, field_goal_result="missed", fixed_drive=3,
             fixed_drive_result="Missed field goal"),
        # Drive 4 (BBB): made FG.
        _row(**B, play_type="run", yards_gained=6, epa=0.3, fixed_drive=4),
        _row(**B, play_type="field_goal", field_goal_attempt=1, field_goal_result="made", fixed_drive=4,
             fixed_drive_result="Field goal", drive_ended_with_score=1),
        # Playoff and null-posteam rows are dropped.
        _row(**A, season_type="POST", play_type="run", yards_gained=50, epa=3.0, fixed_drive=9),
        _row(posteam=None, defteam=None, play_type="pass", yards_gained=5, epa=1.0),
    ]
    return pd.DataFrame(rows)


def test_drives_and_points():
    d = drive_table(_pbp()).set_index(["posteam", "fixed_drive"])
    assert len(d) == 4
    assert d.loc[("AAA", 1), "points"] == 7 and d.loc[("AAA", 1), "scored"]
    assert d.loc[("BBB", 2), "points"] == 0 and not d.loc[("BBB", 2), "scored"]  # defensive TD not counted
    assert d.loc[("BBB", 2), "turnover"]
    assert d.loc[("AAA", 3), "points"] == 0 and not d.loc[("AAA", 3), "scored"]
    assert d.loc[("BBB", 4), "points"] == 3 and d.loc[("BBB", 4), "scored"]


def test_team_components():
    c = team_components(_pbp())
    a, b = c["AAA"]["offense"], c["BBB"]["offense"]
    assert a["plays"] == 4 and a["drives"] == 2
    assert a["yards_per_play"] == pytest.approx(36 / 4)
    assert a["first_down_pct"] == pytest.approx(100 * 1 / 4)
    assert a["third_down_rate"] == pytest.approx(0.5)
    assert a["fg_pct"] == 0.0 and a["xp_pct"] == 1.0
    assert a["pts_per_drive"] == pytest.approx(3.5)
    assert a["score_pct"] == pytest.approx(50.0) and a["turnover_pct"] == 0.0
    assert b["plays"] == 2 and b["drives"] == 2
    assert b["turnover_pct"] == pytest.approx(50.0) and b["score_pct"] == pytest.approx(50.0)
    assert b["fg_pct"] == 1.0 and b["xp_pct"] == 0.0 and b["third_down_rate"] == 0.0
    # Defense is the opponent's offense.
    assert c["BBB"]["defense"]["yards_per_play"] == pytest.approx(a["yards_per_play"])
    assert c["AAA"]["defense"]["pts_per_drive"] == pytest.approx(b["pts_per_drive"])


def test_epa_plays_filters():
    e = epa_plays(_pbp())
    assert len(e) == 6 and set(e["posteam"]) == {"AAA", "BBB"}
    assert e["epa"].notna().all()


def test_first_down_fallback_column():
    df = _pbp().drop(columns=["first_down_pass", "first_down_rush", "first_down_penalty"])
    df["first_down"] = 0
    df.loc[1, "first_down"] = 1
    assert team_components(df)["AAA"]["offense"]["first_down_pct"] == pytest.approx(25.0)
