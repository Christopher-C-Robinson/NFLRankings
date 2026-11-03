"""NFL football weeks run Wednesday through the following Tuesday.

College Football Index chooses one Chicago calendar day for Today's games.
It does not define an NFL week. When a game in this project has a kickoff
date, the week that contains it starts on Wednesday and ends on Tuesday.
The public week control still uses the nflverse week number. If every dated
game in that number shares one window, the label is that window.

A file that only has integer weeks keeps those numbers. ``describe_weeks``
reports ``calendar`` as ``nflverse-week`` in that case so the page can say
the Wednesday rule is waiting on dates.

The default week is the smallest week that still has a game without a final
score. If every game has a final, the default is ``week_max``.
"""

from __future__ import annotations

from datetime import date, timedelta

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def parse_gameday(value) -> date | None:
    """Return a calendar date from ``YYYY-MM-DD``, ignoring a trailing time."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def football_week_window(day: date) -> tuple[date, date]:
    """Wednesday on or before ``day``, through the following Tuesday.

    Wednesday stays in the week that starts that day. Tuesday stays in the
    week that started six days earlier. The date is the kickoff calendar
    date from the schedule, not a UTC conversion of a timestamp.
    """
    # date.weekday(): Monday is 0 and Wednesday is 2.
    start = day - timedelta(days=(day.weekday() - 2) % 7)
    return start, start + timedelta(days=6)


def _pretty(day: date) -> str:
    return f"{_WEEKDAYS[day.weekday()]} {_MONTHS[day.month - 1]} {day.day}"


def select_current_week(games: list[dict], week_max: int | None) -> tuple[int | None, str]:
    """Smallest week with an unplayed game, otherwise ``week_max``.

    The reason is ``unplayed`` or ``week_max`` so the page can say which
    rule it used. ``played`` is false for a game that has no final score.
    """
    unplayed = [int(game["week"]) for game in games if game.get("week") is not None and not game.get("played")]
    if unplayed:
        return min(unplayed), "unplayed"
    if week_max is not None:
        return int(week_max), "week_max"
    scheduled = [int(game["week"]) for game in games if game.get("week") is not None]
    if scheduled:
        return max(scheduled), "week_max"
    return None, "week_max"


def describe_weeks(games: list[dict], week_max: int | None) -> dict:
    """Week catalog for the page: current week, and Wednesday–Tuesday labels."""
    current, reason = select_current_week(games, week_max)
    buckets: dict[int, list[dict]] = {}
    for game in games:
        if game.get("week") is None:
            continue
        buckets.setdefault(int(game["week"]), []).append(game)
    weeks = []
    dated_games = 0
    for week in sorted(buckets):
        windows = []
        undated = 0
        for game in buckets[week]:
            day = parse_gameday(game.get("gameday"))
            if day is None:
                undated += 1
                continue
            windows.append(football_week_window(day))
        dated_games += len(windows)
        entry: dict = {"week": week, "dated_games": len(windows), "undated_games": undated}
        if windows:
            starts = {window[0] for window in windows}
            start = min(window[0] for window in windows)
            end = max(window[1] for window in windows)
            entry.update({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "label": f"{_pretty(start)} – {_pretty(end)}",
                "aligned": len(starts) == 1,
            })
        else:
            entry["aligned"] = False
        weeks.append(entry)
    return {
        "calendar": "wednesday-tuesday" if dated_games else "nflverse-week",
        "current_week": current,
        "current_week_reason": reason,
        "weeks": weeks,
    }
