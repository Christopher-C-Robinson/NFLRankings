"""Division and conference power, fit with team ratings.

College Football Index estimates team ratings and conference strength
together in ``js/conference-model.js`` ``fitConferencePower``
(definition ``conference-power-1``). CFI has no division level and no
conference-power table. The production priors are ``teamPriorGames = 2``
and ``conferencePriorTeams = 1``. The objective is::

    sum_g (cappedMargin_g - venue_g - R_home + R_away)^2
    + teamPriorGames * sum_i (R_i - C_conference(i))^2
    + teamPriorGames * conferencePriorTeams * sum_c C_c^2

``cappedMargin`` clips the final margin at ±28. ``venue`` is the home edge,
and 0 on a neutral site. An independent is not pooled: its conference value
is fixed at 0.

The NFL fit adds the division between the team and the conference::

    sum_g (cappedMargin_g - venue_g - R_home + R_away)^2
    + teamPriorGames * sum_i (R_i - D_division(i))^2
    + teamPriorGames * divisionPriorTeams * sum_d (D_d - C_conference(d))^2
    + teamPriorGames * divisionPriorTeams * conferencePriorDivisions * sum_c C_c^2

A team with no division is pulled toward 0 and does not share a pool. A
division with no conference, or an independent conference, is pulled toward
0. The same games also produce an unpooled team rating whose only prior is
``teamPriorGames`` toward 0. The matchup page's group adjustment is the
change in the margin when the hierarchical ratings replace those unpooled
ratings. That is the CFI conference adjustment, extended through the division.

TODO(holdout): retune ``division_prior_teams`` and
``conference_prior_divisions`` on a frozen pregame holdout before these
ratings are added into the published spread. Do not copy CFI's
``conferencePriorTeams = 1`` onto a four-team NFL division. That prior is
one pseudo-team on conferences that are usually much larger than four
clubs, so the same k is about one fifth of an NFL division. The default
here is half a team (``division_prior_teams = 0.5``), about an 11 percent
share of a four-team division (0.5 / 4.5), nearer the share k = 1 has on a
mid-size college conference. ``conference_prior_divisions = 1`` pulls each
conference toward 0 by one division. ``team_prior_games`` stays 2 because
that prior is per team, the same role as CFI's team prior.
"""

from __future__ import annotations

import math

import numpy as np

DEFINITION = "hierarchy-power-1"
MARGIN_CAP = 28.0
TEAM_PRIOR_GAMES = 2.0
DIVISION_PRIOR_TEAMS = 0.5
CONFERENCE_PRIOR_DIVISIONS = 1.0
TUNING_NOTE = (
    "Team ratings shrink toward the division by 2 games, the same per-team prior "
    "College Football Index uses. Each division shrinks toward its conference by "
    "0.5 team, not by 1: copying the college prior would over-shrink a four-team "
    "division. Each conference shrinks toward zero by 1 division. "
    "These group priors are defaults and still need a pregame holdout. "
    "They are not added to the neutral win-chance rank or the EPA spread."
)


def _pooled_label(value) -> str | None:
    """Return a pool name, or None for a blank or independent membership."""
    if value is None:
        return None
    text = str(value).strip()
    key = " ".join(text.lower().split())
    if not key or key in {"none", "unknown", "null"}:
        return None
    if "independent" in key:
        return None
    return text


def _round(value: float, digits: int = 6) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite group power")
    return round(number, digits)


def _played(game: dict) -> bool:
    if not game.get("played"):
        return False
    try:
        home = float(game["home_score"])
        away = float(game["away_score"])
    except (KeyError, TypeError, ValueError):
        return False
    return math.isfinite(home) and math.isfinite(away)


def _adjusted_margin(game: dict, home_field: float) -> float:
    margin = float(game["home_score"]) - float(game["away_score"])
    margin = max(-MARGIN_CAP, min(MARGIN_CAP, margin))
    venue = 0.0 if game.get("neutral") else home_field
    return margin - venue


def _membership(teams: list[dict]) -> tuple[list[str], dict[str, str | None], dict[str, str | None]]:
    """Team order, each team's division, and each division's conference."""
    order = sorted(str(team["team"]) for team in teams)
    by_team = {str(team["team"]): team for team in teams}
    division_of: dict[str, str | None] = {}
    conference_of_division: dict[str, str | None] = {}
    for abbr in order:
        team = by_team[abbr]
        division = _pooled_label(team.get("division"))
        conference = _pooled_label(team.get("conference"))
        division_of[abbr] = division
        if division is None:
            continue
        if division not in conference_of_division:
            conference_of_division[division] = conference
            continue
        previous = conference_of_division[division]
        if previous != conference:
            raise ValueError(
                f"division {division} is listed in more than one conference ({previous} and {conference})"
            )
    return order, division_of, conference_of_division


def _solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        fitted = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError("group power system is singular") from exc
    if not np.all(np.isfinite(fitted)):
        raise ValueError("group power solve was not finite")
    residual = float(np.max(np.abs(matrix @ fitted - rhs)))
    if residual > 1e-8:
        raise ValueError(f"group power normal residual {residual} is above 1e-8")
    return fitted


def _game_terms(index: dict[str, int], games: list[dict], home_field: float, size: int) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, float]], int]:
    matrix = np.zeros((size, size))
    rhs = np.zeros(size)
    observations: list[tuple[int, int, float]] = []
    used = 0
    for game in games:
        if not _played(game):
            continue
        home = str(game.get("home"))
        away = str(game.get("away"))
        if home not in index or away not in index or home == away:
            continue
        adjusted = _adjusted_margin(game, home_field)
        i = index[home]
        j = index[away]
        matrix[i, i] += 1.0
        matrix[j, j] += 1.0
        matrix[i, j] -= 1.0
        matrix[j, i] -= 1.0
        rhs[i] += adjusted
        rhs[j] -= adjusted
        observations.append((i, j, adjusted))
        used += 1
    return matrix, rhs, observations, used


def fit_group_power(
    teams: list[dict],
    games: list[dict],
    home_field_points: float,
    team_prior_games: float = TEAM_PRIOR_GAMES,
    division_prior_teams: float = DIVISION_PRIOR_TEAMS,
    conference_prior_divisions: float = CONFERENCE_PRIOR_DIVISIONS,
) -> dict:
    """Fit unpooled team ratings and the division/conference hierarchy.

    Ratings are in points. The hierarchy does not replace the EPA win-chance
    board; callers copy the numbers onto the team rows and a summary block.
    """
    home_field = float(home_field_points)
    if not math.isfinite(home_field):
        raise ValueError("home_field_points must be finite")
    for name, value in (
        ("team_prior_games", team_prior_games),
        ("division_prior_teams", division_prior_teams),
        ("conference_prior_divisions", conference_prior_divisions),
    ):
        if not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f"{name} must be a positive finite number")
    team_prior = float(team_prior_games)
    division_weight = team_prior * float(division_prior_teams)
    conference_weight = division_weight * float(conference_prior_divisions)

    order, division_of, conference_of_division = _membership(teams)
    if not order:
        return _empty(home_field, team_prior, division_prior_teams, conference_prior_divisions)
    team_index = {abbr: i for i, abbr in enumerate(order)}
    divisions = sorted(conference_of_division)
    conferences = sorted({name for name in conference_of_division.values() if name})
    division_index = {name: len(order) + i for i, name in enumerate(divisions)}
    conference_index = {name: len(order) + len(divisions) + i for i, name in enumerate(conferences)}

    unpooled_matrix, unpooled_rhs, observations, used = _game_terms(team_index, games, home_field, len(order))
    for i in range(len(order)):
        unpooled_matrix[i, i] += team_prior
    unpooled = _solve(unpooled_matrix, unpooled_rhs)

    size = len(order) + len(divisions) + len(conferences)
    matrix, rhs, observations, used = _game_terms(team_index, games, home_field, size)
    for abbr, i in team_index.items():
        matrix[i, i] += team_prior
        division = division_of[abbr]
        if division is None:
            continue
        d = division_index[division]
        matrix[d, d] += team_prior
        matrix[i, d] -= team_prior
        matrix[d, i] -= team_prior
    division_counts = {name: 0 for name in divisions}
    for division in division_of.values():
        if division is not None:
            division_counts[division] += 1
    conference_division_counts = {name: 0 for name in conferences}
    for division, conference in conference_of_division.items():
        d = division_index[division]
        if conference is None:
            matrix[d, d] += division_weight
            continue
        c = conference_index[conference]
        conference_division_counts[conference] += 1
        matrix[d, d] += division_weight
        matrix[c, c] += division_weight
        matrix[d, c] -= division_weight
        matrix[c, d] -= division_weight
    for conference, c in conference_index.items():
        matrix[c, c] += conference_weight
    fitted = _solve(matrix, rhs)

    team_rows = {}
    for abbr, i in team_index.items():
        division = division_of[abbr]
        conference = conference_of_division.get(division) if division else None
        team_rows[abbr] = {
            "power": float(fitted[i]),
            "unpooled": float(unpooled[i]),
            "division": division,
            "conference": conference,
            "division_power": 0.0 if division is None else float(fitted[division_index[division]]),
            "conference_power": 0.0 if not conference else float(fitted[conference_index[conference]]),
        }
    division_rows = [
        {
            "name": name,
            "conference": conference_of_division[name] or "",
            "points": float(fitted[division_index[name]]),
            "teams": division_counts[name],
        }
        for name in divisions
    ]
    conference_rows = [
        {
            "name": name,
            "points": float(fitted[conference_index[name]]),
            "teams": sum(1 for abbr in order if team_rows[abbr]["conference"] == name),
            "divisions": conference_division_counts[name],
        }
        for name in conferences
    ]
    division_rows.sort(key=lambda row: (-row["points"], row["name"]))
    conference_rows.sort(key=lambda row: (-row["points"], row["name"]))

    residual = 0.0
    for i, j, adjusted in observations:
        residual += (adjusted - fitted[i] + fitted[j]) ** 2
    team_penalty = 0.0
    for abbr, i in team_index.items():
        division = division_of[abbr]
        target = 0.0 if division is None else fitted[division_index[division]]
        team_penalty += team_prior * (fitted[i] - target) ** 2
    division_penalty = 0.0
    for division, conference in conference_of_division.items():
        target = 0.0 if conference is None else fitted[conference_index[conference]]
        division_penalty += division_weight * (fitted[division_index[division]] - target) ** 2
    conference_penalty = conference_weight * sum(float(fitted[conference_index[name]]) ** 2 for name in conferences)
    return {
        "definition": DEFINITION,
        "margin_cap": MARGIN_CAP,
        "team_prior_games": team_prior,
        "division_prior_teams": float(division_prior_teams),
        "conference_prior_divisions": float(conference_prior_divisions),
        "home_field_points": home_field,
        "tuning": TUNING_NOTE,
        "team_powers": team_rows,
        "divisions": division_rows,
        "conferences": conference_rows,
        "diagnostics": {
            "played_games": used,
            "teams": len(order),
            "divisions": len(divisions),
            "conferences": len(conferences),
            "residual_sum_squares": residual,
            "team_penalty": team_penalty,
            "division_penalty": division_penalty,
            "conference_penalty": conference_penalty,
            "objective": residual + team_penalty + division_penalty + conference_penalty,
            "unpooled_normal_residual": float(np.max(np.abs(unpooled_matrix @ unpooled - unpooled_rhs))),
            "normal_residual": float(np.max(np.abs(matrix @ fitted - rhs))),
        },
    }


def _empty(home_field: float, team_prior: float, division_prior: float, conference_prior: float) -> dict:
    return {
        "definition": DEFINITION,
        "margin_cap": MARGIN_CAP,
        "team_prior_games": team_prior,
        "division_prior_teams": float(division_prior),
        "conference_prior_divisions": float(conference_prior),
        "home_field_points": home_field,
        "tuning": TUNING_NOTE,
        "team_powers": {},
        "divisions": [],
        "conferences": [],
        "diagnostics": {
            "played_games": 0,
            "teams": 0,
            "divisions": 0,
            "conferences": 0,
            "residual_sum_squares": 0.0,
            "team_penalty": 0.0,
            "division_penalty": 0.0,
            "conference_penalty": 0.0,
            "objective": 0.0,
            "unpooled_normal_residual": 0.0,
            "normal_residual": 0.0,
        },
    }


def _public_number(value: float) -> float:
    return _round(value)


def attach_group_power(teams: list[dict], games: list[dict], home_field_points: float) -> dict:
    """Copy the fit onto each team and return the summary stored on the season."""
    fitted = fit_group_power(teams, games, home_field_points)
    powers = fitted["team_powers"]
    for team in teams:
        info = powers.get(str(team["team"]))
        if info is None:
            continue
        team["hierarchy_power"] = _public_number(info["power"])
        team["unpooled_power"] = _public_number(info["unpooled"])
        team["division_power"] = _public_number(info["division_power"])
        team["conference_power"] = _public_number(info["conference_power"])
    summary = {
        "definition": fitted["definition"],
        "margin_cap": fitted["margin_cap"],
        "team_prior_games": fitted["team_prior_games"],
        "division_prior_teams": fitted["division_prior_teams"],
        "conference_prior_divisions": fitted["conference_prior_divisions"],
        "home_field_points": _public_number(fitted["home_field_points"]),
        "tuning": fitted["tuning"],
        "conferences": [
            {
                "name": row["name"],
                "points": _public_number(row["points"]),
                "teams": row["teams"],
                "divisions": row["divisions"],
            }
            for row in fitted["conferences"]
        ],
        "divisions": [
            {
                "name": row["name"],
                "conference": row["conference"],
                "points": _public_number(row["points"]),
                "teams": row["teams"],
            }
            for row in fitted["divisions"]
        ],
        "diagnostics": {key: _public_number(value) if isinstance(value, float) else value for key, value in fitted["diagnostics"].items()},
    }
    return summary
