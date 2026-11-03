"""Walk-forward aspect weights on top of the scrimmage-EPA spread.

The published pregame number is schedule-adjusted scrimmage EPA, blended with
last season at 14 games, then converted with the shipped point scale. This
module asks whether the rest of the game should move that number. It fits one
ridge of residual points on many aspect gaps. The fit for a season uses only
earlier seasons, in a rolling window, with more weight on the recent ones.
2024 and 2025 are the check. 2026 is reported and is not used to pick the
window, the penalty, or which aspects exist.

Nothing here reads the network or the published JSON. ``scripts/screen_aspects.py``
builds the game table. The spread changes only when that screen's promotion
flag is true.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .rating import ITERATIONS
from .winprob import win_probability

# Trailing seasons in the fit. Four is long enough for a ridge and short
# enough that a 2018 slope does not still run a 2025 game.
WINDOW_SEASONS = 4
# A season two years back counts half as much as the latest prior season.
HALF_LIFE_SEASONS = 2.0
# Penalty is this many times the sum of sample weights, added to each
# standardized column. Chosen inside the training window, never on the check.
LAMBDAS = (0.01, 0.1, 1.0, 10.0, 100.0)
# Scored seasons. Training rows may start earlier than SCORE_FIRST.
SCORE_FIRST = 2018
CHECK_SEASONS = (2024, 2025)
REPORT_SEASON = 2026
# Points per standard deviation, for the written inventory only. A smaller
# weight is still inside the ridge. It is not a second feature screen.
WEIGHT_FLOOR = 0.25
_MIN_TRAIN = 50
_MIN_HOLD = 20
_STD_FLOOR = 1e-8


class Feature:
    """One pregame column and the part of the game it comes from."""

    def __init__(self, name: str, group: str, summary: str) -> None:
        self.name = name
        self.group = group
        self.summary = summary


# The ridge sees every column. Groups are only for the written ablation.
FEATURES: tuple[Feature, ...] = (
    Feature("pass_matchup", "style", "Pass EPA of the home offense against the away pass defense, minus the swap."),
    Feature("rush_matchup", "style", "Rush EPA of the home offense against the away rush defense, minus the swap."),
    Feature("pass_exposed", "style", "Pass matchup weighted by each offense's passing share."),
    Feature("rush_exposed", "style", "Rush matchup weighted by each offense's rushing share."),
    Feature("early_matchup", "phase", "Early-down EPA matchup, first and second down."),
    Feature("late_matchup", "phase", "Late-down EPA matchup, third and fourth down."),
    Feature("redzone_matchup", "phase", "EPA matchup inside the opponent's 20."),
    Feature("comp_matchup", "phase", "EPA matchup on plays with pre-play win probability from 10% to 90%."),
    Feature("success_matchup", "rates", "Success-rate matchup."),
    Feature("explosive_matchup", "rates", "Explosiveness matchup, 20-yard passes and 10-yard runs."),
    Feature("ypp_matchup", "rates", "Yards-per-play matchup."),
    Feature("turnover_matchup", "ball", "Matchup of plays without an interception or a lost fumble."),
    Feature("sack_matchup", "ball", "Matchup of pass plays that are not sacks."),
    Feature("pressure_matchup", "ball", "Matchup of pass plays without a quarterback hit or a sack."),
    Feature("penalty_matchup", "ball", "Matchup of penalty yards, with a defensive penalty as a plus for the offense."),
    Feature("start_matchup", "drive", "Matchup of drive-start yards from the offense's own goal."),
    Feature("ppd_matchup", "drive", "Points-per-drive matchup."),
    Feature("score_drive_matchup", "drive", "Share of drives that end in a touchdown or a field goal."),
    Feature("clean_drive_matchup", "drive", "Share of drives that do not end in a turnover."),
    Feature("st_matchup", "special", "Special-teams EPA matchup on kickoffs, punts, field goals, and extra points."),
    Feature("rest_diff", "situation", "Home rest days minus away rest days, from the schedule."),
    Feature("travel_diff", "situation", "Away travel miles minus home travel miles, in thousands."),
    Feature("wind_pass", "situation", "Wind speed times how much more the away team passes."),
    Feature("cold_pass", "situation", "Degrees under 45, when a temperature is listed, times the away passing edge."),
    Feature("qb_edge", "personnel", "Shrunk career pass EPA of the expected home starter minus the away starter."),
    Feature("out_diff", "personnel", "Players ruled out for the away team minus players ruled out for the home team."),
)

FEATURE_NAMES: tuple[str, ...] = tuple(feature.name for feature in FEATURES)


def feature_groups() -> dict[str, tuple[str, ...]]:
    """Aspect names grouped for the ablation table."""
    groups: dict[str, list[str]] = {}
    for feature in FEATURES:
        groups.setdefault(feature.group, []).append(feature.name)
    return {name: tuple(columns) for name, columns in groups.items()}


def unit_matchup(off_home: float, def_home: float, off_away: float, def_away: float) -> float:
    """Home offense versus away defense, minus the swapped matchup.

    ``def_home`` is the home defense. Swapping the clubs negates the result,
    so a neutral site does not need a separate formula.
    """
    return (off_home - def_away) - (off_away - def_home)


def expected_starter(ladder: Sequence[str], unavailable: set[str]) -> str | None:
    """First quarterback on the chart who is not out or doubtful."""
    for player_id in ladder:
        if player_id and player_id not in unavailable:
            return player_id
    return None


def report_on_or_before(modified_date, game_date) -> bool:
    """True when an injury timestamp is missing or not after the game date.

    A missing timestamp cannot be placed after the game, so the week's row
    stays. Callers that have a timestamp drop a report dated after kickoff day.
    """
    if modified_date is None or pd.isna(modified_date):
        return True
    if game_date is None or pd.isna(game_date):
        return True
    return modified_date <= game_date


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle miles between two WGS84 points."""
    radius = 3958.8
    p1, l1, p2, l2 = (math.radians(value) for value in (lat1, lon1, lat2, lon2))
    dlat = p2 - p1
    dlon = l2 - l1
    hav = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.asin(min(1.0, math.sqrt(hav)))


def adjust_components(frame: pd.DataFrame, iterations: int = ITERATIONS) -> pd.DataFrame:
    """Opponent-adjust a rate, leaving a missing side missing.

    Same iteration as ``rating.adjust`` when every team has offensive and
    defensive rows. A team with no offensive rows does not get a fake zero,
    and that hole is left out of the other teams' opponent averages.
    Columns in, and in the result: the result has ``off_adj``, ``def_adj``,
    ``off_n``, and ``def_n``, indexed by team.
    """
    empty = pd.DataFrame(columns=["off_adj", "def_adj", "off_n", "def_n"])
    if frame.empty or not {"posteam", "defteam", "epa"}.issubset(frame.columns):
        return empty
    work = frame.loc[frame["posteam"].notna() & frame["defteam"].notna() & frame["epa"].notna(), ["posteam", "defteam", "epa"]]
    if work.empty:
        return empty
    off = work.groupby("posteam")["epa"].agg(off="mean", off_n="size")
    deff = work.groupby("defteam")["epa"].agg(**{"def_raw": "mean", "def_n": "size"})
    teams = sorted(set(off.index) | set(deff.index))
    if len(teams) < 2:
        raw_off = off["off"].reindex(teams)
        raw_def = deff["def_raw"].reindex(teams)
        return pd.DataFrame({
            "off_adj": raw_off,
            "def_adj": raw_def,
            "off_n": off["off_n"].reindex(teams).fillna(0).astype(int),
            "def_n": deff["def_n"].reindex(teams).fillna(0).astype(int),
        })
    raw_off = off["off"].reindex(teams)
    raw_def = deff["def_raw"].reindex(teams)
    off_n = off["off_n"].reindex(teams).fillna(0).astype(int)
    def_n = deff["def_n"].reindex(teams).fillna(0).astype(int)
    seen_off = raw_off.notna()
    seen_def = raw_def.notna()
    off_mean = float(raw_off.mean())
    def_mean = float(raw_def.mean())
    pair = (
        work.groupby(["posteam", "defteam"]).size().unstack(fill_value=0)
        .reindex(index=teams, columns=teams, fill_value=0).astype(float)
    )
    off_w = pair.div(pair.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    def_w = pair.T
    def_w = def_w.div(def_w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    if not bool(seen_off.all() and seen_def.all()):
        off_w.loc[:, ~seen_def.to_numpy()] = 0.0
        off_w = off_w.div(off_w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
        def_w.loc[:, ~seen_off.to_numpy()] = 0.0
        def_w = def_w.div(def_w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    adj_off = raw_off.fillna(off_mean).to_numpy(dtype=float)
    adj_def = raw_def.fillna(def_mean).to_numpy(dtype=float)
    raw_off_v = raw_off.fillna(off_mean).to_numpy(dtype=float)
    raw_def_v = raw_def.fillna(def_mean).to_numpy(dtype=float)
    off_m = off_w.to_numpy(dtype=float)
    def_m = def_w.to_numpy(dtype=float)
    seen_off_v = seen_off.to_numpy()
    seen_def_v = seen_def.to_numpy()
    for _ in range(iterations):
        sos_off = off_m @ adj_def
        sos_def = def_m @ adj_off
        adj_off = raw_off_v - sos_off
        adj_def = raw_def_v - sos_def
        adj_off = adj_off - adj_off[seen_off_v].mean() + off_mean
        adj_def = adj_def - adj_def[seen_def_v].mean() + def_mean
        adj_off = np.where(seen_off_v, adj_off, off_mean)
        adj_def = np.where(seen_def_v, adj_def, def_mean)
    return pd.DataFrame({
        "off_adj": np.where(seen_off_v, adj_off, np.nan),
        "def_adj": np.where(seen_def_v, adj_def, np.nan),
        "off_n": off_n.to_numpy(),
        "def_n": def_n.to_numpy(),
    }, index=teams)


def season_weight(season: int, latest: int, half_life: float | None) -> float:
    """Weight of one training season. The latest prior season weighs 1.

    ``half_life`` of None gives every season the same weight. A finite
    half-life cuts the weight in half every that many seasons of age.
    """
    if half_life is None:
        return 1.0
    if half_life <= 0:
        raise ValueError("half_life must be positive")
    return 0.5 ** ((int(latest) - int(season)) / float(half_life))


def prior_seasons(seasons: Sequence[int], target: int, window: int | None) -> list[int]:
    """Seasons strictly before ``target``, keeping the trailing window."""
    prior = sorted({int(season) for season in seasons if int(season) < int(target)})
    if window is None:
        return prior
    if window < 1:
        raise ValueError("window must be at least 1")
    return prior[-int(window):]


@dataclass(frozen=True)
class Fit:
    """Standardized ridge for one target season. An empty feature list predicts the baseline."""

    features: tuple[str, ...]
    mean: tuple[float, ...]
    std: tuple[float, ...]
    beta: tuple[float, ...]
    lam: float
    train_seasons: tuple[int, ...]
    train_games: int

    def as_dict(self) -> dict:
        points = {name: float(value) for name, value in zip(self.features, self.beta)}
        return {
            "lambda": self.lam,
            "train_seasons": list(self.train_seasons),
            "train_games": self.train_games,
            "beta_points_per_sd": points,
        }


def _zero_fit(lam: float = 0.0) -> Fit:
    return Fit((), (), (), (), lam, (), 0)


def _design(frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return np.column_stack([pd.to_numeric(frame[name], errors="coerce").fillna(0.0).to_numpy(dtype=float) for name in features])


def _fit_beta(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: int,
    window: int | None,
    half_life: float | None,
    lam: float,
) -> Fit:
    """Ridge of ``margin - base`` on seasons before ``target``. No intercept.

    There is no intercept because every feature is a home-minus-away gap.
    An intercept would favor the home team twice, once here and once in the
    baseline home field.
    """
    seasons = prior_seasons(frame["season"].unique(), target, window)
    if not seasons or not features:
        return _zero_fit(lam)
    train = frame[frame["season"].isin(seasons)]
    if len(train) < _MIN_TRAIN:
        return _zero_fit(lam)
    latest = max(seasons)
    weights = np.array([season_weight(int(season), latest, half_life) for season in train["season"]], dtype=float)
    y = (train["margin"].to_numpy(dtype=float) - train["base"].to_numpy(dtype=float))
    raw = _design(train, features)
    keep: list[int] = []
    means: list[float] = []
    stds: list[float] = []
    wsum = float(weights.sum())
    for index in range(raw.shape[1]):
        column = raw[:, index]
        mean = float(np.dot(weights, column) / wsum)
        var = float(np.dot(weights, (column - mean) ** 2) / wsum)
        std = math.sqrt(var)
        if std >= _STD_FLOOR:
            keep.append(index)
            means.append(mean)
            stds.append(std)
    if not keep:
        return Fit((), (), (), (), lam, tuple(seasons), int(len(train)))
    kept_names = tuple(features[index] for index in keep)
    z = (raw[:, keep] - np.array(means)) / np.array(stds)
    scale = np.sqrt(weights)
    zw = z * scale[:, None]
    yw = y * scale
    xtx = zw.T @ zw
    penalty = float(lam) * wsum
    xtx.flat[:: xtx.shape[0] + 1] += penalty
    xty = zw.T @ yw
    try:
        beta = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(xtx, xty, rcond=None)[0]
    return Fit(
        kept_names,
        tuple(float(value) for value in means),
        tuple(float(value) for value in stds),
        tuple(float(value) for value in beta),
        float(lam),
        tuple(int(season) for season in seasons),
        int(len(train)),
    )


def apply_fit(frame: pd.DataFrame, fit: Fit) -> np.ndarray:
    """Baseline margin plus the stored correction. Missing feature cells count as 0."""
    base = frame["base"].to_numpy(dtype=float)
    if not fit.features:
        return base.copy()
    total = base.copy()
    for name, mean, std, beta in zip(fit.features, fit.mean, fit.std, fit.beta):
        column = pd.to_numeric(frame[name], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        total = total + beta * (column - mean) / std
    return total


def score_margins(actual: np.ndarray, predicted: np.ndarray, scale: float) -> dict:
    """Winner hits, Brier, and margin MAE on one row set.

    Ties stay out of the winner count and the Brier score. A predicted margin
    of exactly 0 stays out of the winner count and still scores as 1/2 in the
    Brier score. MAE uses every game, including ties.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    decisive = actual != 0
    graded = decisive & (predicted != 0)
    hits = int(((predicted > 0) == (actual > 0))[graded].sum())
    graded_n = int(graded.sum())
    if decisive.any():
        prob = np.array([win_probability(float(value), scale) for value in predicted[decisive]])
        outcome = (actual[decisive] > 0).astype(float)
        brier = float(np.mean((prob - outcome) ** 2))
    else:
        brier = float("nan")
    mae = float(np.mean(np.abs(actual - predicted))) if len(actual) else float("nan")
    return {"hits": hits, "n": graded_n, "brier": brier, "mae": mae, "games": int(len(actual))}


def _better(hits: int, brier: float, lam: float, best: tuple[int, float, float] | None) -> bool:
    if best is None:
        return True
    if hits != best[0]:
        return hits > best[0]
    if abs(brier - best[1]) > 1e-12:
        return brier < best[1]
    return lam > best[2]


def choose_lambda(
    frame: pd.DataFrame,
    features: Sequence[str],
    window_seasons: Sequence[int],
    window: int | None,
    half_life: float | None,
    lambdas: Sequence[float],
    scale: float,
) -> float:
    """Pick the penalty by walk-forward inside the training window.

    The holdout season is not in its own fit, and neither is any later season.
    """
    best: tuple[int, float, float] | None = None
    chosen = max(lambdas)
    seasons = list(window_seasons)
    for lam in lambdas:
        actuals: list[np.ndarray] = []
        preds: list[np.ndarray] = []
        used = False
        for hold in seasons:
            held = frame[frame["season"].eq(hold)]
            if len(held) < _MIN_HOLD:
                continue
            fit = _fit_beta(frame[frame["season"].isin(seasons)], features, int(hold), window, half_life, float(lam))
            if fit.train_games < _MIN_TRAIN:
                continue
            used = True
            actuals.append(held["margin"].to_numpy(dtype=float))
            preds.append(apply_fit(held, fit))
        if not used:
            continue
        scored = score_margins(np.concatenate(actuals), np.concatenate(preds), scale)
        if _better(scored["hits"], scored["brier"], float(lam), best):
            best = (scored["hits"], scored["brier"], float(lam))
            chosen = float(lam)
    return chosen


def fit_season(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: int,
    scale: float,
    window: int | None = WINDOW_SEASONS,
    half_life: float | None = HALF_LIFE_SEASONS,
    lambdas: Sequence[float] = LAMBDAS,
) -> Fit:
    """Fit one target season from earlier seasons only."""
    seasons = prior_seasons(frame["season"].unique(), target, window)
    if not seasons:
        return _zero_fit(max(lambdas))
    lam = choose_lambda(frame, features, seasons, window, half_life, lambdas, scale)
    pool = frame[frame["season"].isin(seasons)]
    return _fit_beta(pool, features, target, window, half_life, lam)


def predict_seasons(
    frame: pd.DataFrame,
    features: Sequence[str],
    targets: Sequence[int],
    scale: float,
    window: int | None = WINDOW_SEASONS,
    half_life: float | None = HALF_LIFE_SEASONS,
    lambdas: Sequence[float] = LAMBDAS,
) -> tuple[pd.Series, dict[int, Fit]]:
    """Walk-forward predictions indexed like ``frame``. Other rows stay at the baseline."""
    predicted = frame["base"].astype(float).copy()
    fits: dict[int, Fit] = {}
    for target in targets:
        fit = fit_season(frame, features, int(target), scale, window, half_life, lambdas)
        mask = frame["season"].eq(int(target))
        predicted.loc[mask] = apply_fit(frame.loc[mask], fit)
        fits[int(target)] = fit
    return predicted, fits


def _year_scores(frame: pd.DataFrame, predicted: pd.Series, scale: float, years: Sequence[int]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    values = predicted.to_numpy(dtype=float)
    for year in years:
        mask = frame["season"].eq(int(year)).to_numpy()
        scored = score_margins(frame.loc[mask, "margin"].to_numpy(dtype=float), values[mask], scale)
        if int(year) == REPORT_SEASON:
            early = mask & frame["week"].le(4).to_numpy()
            late = mask & frame["week"].ge(5).to_numpy()
            scored["weeks_1_4"] = score_margins(frame.loc[early, "margin"].to_numpy(dtype=float), values[early], scale)
            scored["weeks_5_plus"] = score_margins(frame.loc[late, "margin"].to_numpy(dtype=float), values[late], scale)
        out[str(year)] = scored
    return out


def beats_both(model: Mapping[str, Mapping], baseline: Mapping[str, Mapping], years: Sequence[int] = CHECK_SEASONS) -> bool:
    """True when winner hits rise and Brier does not rise, on each check season.

    The two seasons are the same games for both models. A tie on hits is not
    a gain. Brier may tie. A gain on only one season is not enough.
    """
    for year in years:
        key = str(year)
        if key not in model or key not in baseline:
            return False
        if int(model[key]["n"]) != int(baseline[key]["n"]) or int(model[key]["n"]) <= 0:
            return False
        if int(model[key]["hits"]) <= int(baseline[key]["hits"]):
            return False
        model_brier = float(model[key]["brier"])
        base_brier = float(baseline[key]["brier"])
        if not math.isfinite(model_brier) or not math.isfinite(base_brier):
            return False
        if model_brier > base_brier + 1e-12:
            return False
    return True


def _round_score(scored: dict) -> dict:
    out = {
        "hits": int(scored["hits"]),
        "n": int(scored["n"]),
        "brier": None if not math.isfinite(scored["brier"]) else round(float(scored["brier"]), 6),
        "mae": None if not math.isfinite(scored["mae"]) else round(float(scored["mae"]), 4),
        "games": int(scored["games"]),
    }
    for key in ("weeks_1_4", "weeks_5_plus"):
        if key in scored:
            out[key] = _round_score(scored[key])
    return out


def closing_line_scores(frame: pd.DataFrame, years: Sequence[int]) -> dict[str, dict]:
    """Hard closing-line winners.

    In the nflverse schedule file, ``spread_line`` is the home team's closing
    margin: positive when the home team is favored. Pushes and ties are left
    out. The line is not a model input. Flipping this sign misses the
    published 1,407-of-2,119 comparison, so the sign is part of the scorer.
    """
    if "spread_line" not in frame.columns:
        return {}
    spread = pd.to_numeric(frame["spread_line"], errors="coerce")
    margin = frame["margin"].to_numpy(dtype=float)
    out = {}
    for year in years:
        mask = frame["season"].eq(int(year)).to_numpy()
        line = spread.to_numpy(dtype=float)[mask]
        actual = margin[mask]
        usable = np.isfinite(line) & (line != 0) & (actual != 0)
        pick_home = line > 0
        hits = int((pick_home == (actual > 0))[usable].sum())
        out[str(year)] = {"hits": hits, "n": int(usable.sum())}
    return out


def evaluate(frame: pd.DataFrame, scale: float, features: Sequence[str] | None = None) -> dict:
    """Score the predeclared dynamic ridge against the baseline on one game table.

    The dynamic model is the only promotion candidate. A frozen equal-weight
    ridge on 2018–2023 is reported so a reader can see whether time-varying
    weights mattered. It is not allowed to replace the dynamic model after
    the check seasons are known. Ablations refit 2021–2023 only.
    """
    names = tuple(features) if features is not None else FEATURE_NAMES
    missing = [name for name in names if name not in frame.columns]
    if missing:
        raise ValueError(f"game table is missing {missing}")
    years = list(range(SCORE_FIRST, REPORT_SEASON + 1))
    dynamic_pred, fits = predict_seasons(frame, names, years, scale)
    static_fit = fit_season(
        frame[frame["season"].between(SCORE_FIRST, CHECK_SEASONS[0] - 1)],
        names,
        CHECK_SEASONS[0],
        scale,
        window=None,
        half_life=None,
    )
    static_pred = frame["base"].astype(float).copy()
    static_pred.loc[:] = apply_fit(frame, static_fit)
    baseline_pred = frame["base"].astype(float)
    accuracy = {
        "baseline": _year_scores(frame, baseline_pred, scale, years),
        "dynamic": _year_scores(frame, dynamic_pred, scale, years),
        "static_frozen": _year_scores(frame, static_pred, scale, years),
    }
    pooled = {}
    for label, span in (("2018_2023", range(2018, 2024)), ("2024_2025", CHECK_SEASONS)):
        mask = frame["season"].isin(span)
        pooled[label] = {}
        for name, pred in (("baseline", baseline_pred), ("dynamic", dynamic_pred), ("static_frozen", static_pred)):
            pooled[label][name] = _round_score(score_margins(
                frame.loc[mask, "margin"].to_numpy(dtype=float),
                pred.loc[mask].to_numpy(dtype=float),
                scale,
            ))
    promoted = beats_both(accuracy["dynamic"], accuracy["baseline"])
    weight_rows = []
    for year in years:
        fit = fits[year]
        weight_rows.append({"season": year, **fit.as_dict()})
    leaders = _leaders(fits)
    ablations = {}
    groups = feature_groups()
    dev_years = (2021, 2022, 2023)
    full_dev, _ = predict_seasons(frame, names, dev_years, scale)
    ablations["full"] = _round_score(score_margins(
        frame.loc[frame["season"].isin(dev_years), "margin"].to_numpy(dtype=float),
        full_dev.loc[frame["season"].isin(dev_years)].to_numpy(dtype=float),
        scale,
    ))
    for group, columns in groups.items():
        kept = tuple(name for name in names if name not in columns)
        pred, _ = predict_seasons(frame, kept, dev_years, scale)
        mask = frame["season"].isin(dev_years)
        ablations[f"without_{group}"] = _round_score(score_margins(
            frame.loc[mask, "margin"].to_numpy(dtype=float),
            pred.loc[mask].to_numpy(dtype=float),
            scale,
        ))
    return {
        "method": "rolling-ridge-aspects-v1",
        "promoted": promoted,
        "decision": (
            "Use the dynamic aspect correction in the pregame spread."
            if promoted else
            "Keep the published pregame spread on scrimmage EPA. The dynamic ridge did not raise winners on both 2024 and 2025 without raising Brier."
        ),
        "window_seasons": WINDOW_SEASONS,
        "half_life_seasons": HALF_LIFE_SEASONS,
        "lambdas": list(LAMBDAS),
        "check_seasons": list(CHECK_SEASONS),
        "report_season": REPORT_SEASON,
        "weight_floor_points": WEIGHT_FLOOR,
        "features": [{"name": feature.name, "group": feature.group, "summary": feature.summary} for feature in FEATURES if feature.name in names],
        "accuracy": {key: {year: _round_score(scored) for year, scored in table.items()} for key, table in accuracy.items()},
        "pooled": pooled,
        "weights_by_season": weight_rows,
        "weight_leaders": leaders,
        "in_the_spread": [row["name"] for row in leaders if row["mean_abs_beta"] >= WEIGHT_FLOOR] if promoted else [],
        "ablation_2021_2023": ablations,
        "static_fit": static_fit.as_dict(),
        "closing_line": closing_line_scores(frame, years),
    }


def _leaders(fits: Mapping[int, Fit]) -> list[dict]:
    """Mean absolute standardized weight on the two check seasons' fits.

    Those fits were trained on earlier seasons. The check results do not
    enter the weights. The floor only labels the table.
    """
    totals: dict[str, list[float]] = {}
    for year in CHECK_SEASONS:
        fit = fits.get(year)
        if fit is None:
            continue
        seen = set(fit.features)
        for name, beta in zip(fit.features, fit.beta):
            totals.setdefault(name, []).append(abs(beta))
        for feature in FEATURES:
            if feature.name not in seen:
                totals.setdefault(feature.name, []).append(0.0)
    rows = []
    for name, values in totals.items():
        rows.append({
            "name": name,
            "mean_abs_beta": round(float(np.mean(values)), 4),
            "carries_weight": float(np.mean(values)) >= WEIGHT_FLOOR,
        })
    rows.sort(key=lambda row: (-row["mean_abs_beta"], row["name"]))
    return rows
