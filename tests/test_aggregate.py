"""Scrimmage-play filters for the EPA rating. No network."""

import pandas as pd

from nflrankings.aggregate import epa_plays


def _row(**kw):
    base = dict(
        game_id="g1", season_type="REG", week=1, posteam="AAA", defteam="BBB",
        play_type="pass", epa=0.2, two_point_attempt=0,
    )
    base.update(kw)
    return base


def test_epa_plays_keep_regular_season_scrimmage_only():
    frame = pd.DataFrame([
        _row(epa=0.4),
        _row(play_type="run", epa=-0.2),
        _row(play_type="kickoff", epa=1.0),
        _row(play_type="no_play", epa=1.0),
        _row(play_type="extra_point", epa=0.1),
        _row(two_point_attempt=1, play_type="pass", epa=2.0),
        _row(no_play=1, epa=3.0),
        _row(season_type="POST", epa=4.0),
        _row(posteam=None, defteam=None, epa=5.0),
        _row(epa=float("nan")),
    ])
    plays = epa_plays(frame)
    assert len(plays) == 2
    assert set(plays["posteam"]) == {"AAA"}
    assert plays["epa"].tolist() == [0.4, -0.2]
