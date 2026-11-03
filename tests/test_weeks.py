"""Wednesday–Tuesday windows and the unplayed-week default. No network."""

from datetime import date

from nflrankings.weeks import describe_weeks, football_week_window, select_current_week


def test_window_starts_wednesday_and_ends_tuesday():
    # 2026-11-03 is a Tuesday. 2026-09-09 is a Wednesday.
    start, end = football_week_window(date(2026, 11, 3))
    assert (start, end) == (date(2026, 10, 28), date(2026, 11, 3))
    assert start.weekday() == 2 and end.weekday() == 1
    assert football_week_window(date(2026, 9, 9)) == (date(2026, 9, 9), date(2026, 9, 15))
    assert football_week_window(date(2026, 9, 15)) == (date(2026, 9, 9), date(2026, 9, 15))
    assert football_week_window(date(2026, 9, 16)) == (date(2026, 9, 16), date(2026, 9, 22))
    assert football_week_window(date(2026, 11, 4)) == (date(2026, 11, 4), date(2026, 11, 10))


def test_current_week_is_the_smallest_unplayed_week():
    games = [
        {"week": 1, "played": True},
        {"week": 2, "played": True},
        {"week": 2, "played": False},
        {"week": 3, "played": False},
    ]
    assert select_current_week(games, 1) == (2, "unplayed")


def test_current_week_falls_back_to_week_max_when_every_game_has_a_final():
    games = [{"week": 1, "played": True}, {"week": 18, "played": True}]
    assert select_current_week(games, 18) == (18, "week_max")
    assert select_current_week([], 8) == (8, "week_max")


def test_missing_dates_keep_the_integer_week():
    catalog = describe_weeks(
        [{"week": 4, "played": False}, {"week": 3, "played": True}],
        3,
    )
    assert catalog["calendar"] == "nflverse-week"
    assert catalog["current_week"] == 4
    assert catalog["current_week_reason"] == "unplayed"
    assert catalog["weeks"][0]["aligned"] is False
    assert "start" not in catalog["weeks"][0]


def test_dated_games_share_one_wednesday_window():
    catalog = describe_weeks(
        [
            {"week": 1, "played": True, "gameday": "2026-09-09"},
            {"week": 1, "played": True, "gameday": "2026-09-14"},
            {"week": 8, "played": False, "gameday": "2026-11-02"},
        ],
        8,
    )
    assert catalog["calendar"] == "wednesday-tuesday"
    assert catalog["current_week"] == 8
    week1, week8 = catalog["weeks"]
    assert week1["aligned"] is True
    assert week1["start"] == "2026-09-09"
    assert week1["end"] == "2026-09-15"
    assert week1["label"].startswith("Wed Sep 9")
    assert week8["start"] == "2026-10-28"
    assert week8["end"] == "2026-11-03"


def test_a_week_that_crosses_tuesday_is_marked_unaligned():
    catalog = describe_weeks(
        [
            {"week": 1, "played": True, "gameday": "2026-09-09"},
            {"week": 1, "played": True, "gameday": "2026-09-16"},
        ],
        1,
    )
    row = catalog["weeks"][0]
    assert row["aligned"] is False
    assert row["start"] == "2026-09-09"
    assert row["end"] == "2026-09-22"
