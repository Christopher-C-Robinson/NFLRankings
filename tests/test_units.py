"""Drive and special-teams observations. No network."""

import pandas as pd

from nflrankings.units import (
    drive_start_observations,
    explosive_observations,
    special_teams_observations,
    success_observations,
)


def _play(**kwargs):
    base = dict(
        game_id="g1",
        season_type="REG",
        week=1,
        play_id=1,
        fixed_drive=1,
        posteam="AAA",
        defteam="BBB",
        play_type="pass",
        epa=0.2,
        success=1,
        yards_gained=5,
        yardline_100=75,
        two_point_attempt=0,
    )
    base.update(kwargs)
    return base


def test_special_teams_keep_kicks_and_drop_scrimmage():
    frame = pd.DataFrame([
        _play(play_type="pass", epa=0.4),
        _play(play_type="kickoff", epa=0.3, play_id=2),
        _play(play_type="punt", epa=-0.1, play_id=3),
        _play(play_type="field_goal", epa=0.5, play_id=4),
        _play(play_type="extra_point", epa=0.02, play_id=5),
        _play(play_type="kickoff", epa=1.0, season_type="POST", play_id=6),
        _play(play_type="punt", epa=None, play_id=7),
    ])
    out = special_teams_observations(frame)
    assert out["epa"].tolist() == [0.3, -0.1, 0.5, 0.02]
    assert set(out.columns) == {"week", "posteam", "defteam", "epa"}


def test_drive_start_uses_the_first_scrimmage_snap():
    frame = pd.DataFrame([
        _play(play_type="kickoff", play_id=1, yardline_100=35, epa=-0.2),
        _play(play_type="run", play_id=2, yardline_100=80, yards_gained=3),
        _play(play_type="pass", play_id=3, yardline_100=70, yards_gained=10),
        _play(game_id="g1", fixed_drive=2, play_type="pass", play_id=10, yardline_100=40, posteam="BBB", defteam="AAA"),
        _play(play_type="run", play_id=4, yardline_100=None, fixed_drive=3),
        _play(season_type="POST", play_type="run", play_id=20, yardline_100=50, fixed_drive=4),
    ])
    out = drive_start_observations(frame)
    assert out["epa"].tolist() == [20.0, 60.0]
    assert out["posteam"].tolist() == ["AAA", "BBB"]


def test_success_and_explosive_flags_follow_the_scrimmage_rules():
    frame = pd.DataFrame([
        _play(play_type="pass", yards_gained=20, success=1),
        _play(play_type="pass", play_id=2, yards_gained=19, success=0),
        _play(play_type="run", play_id=3, yards_gained=10, success=1),
        _play(play_type="run", play_id=4, yards_gained=9, success=0),
        _play(play_type="kickoff", play_id=5, yards_gained=40, success=1),
        _play(play_type="pass", play_id=6, two_point_attempt=1, yards_gained=25, success=1),
    ])
    success = success_observations(frame)
    explosive = explosive_observations(frame)
    assert success["epa"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert explosive["epa"].tolist() == [1.0, 0.0, 1.0, 0.0]
