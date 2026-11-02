"""Download nflverse data, aggregate, rate and write JSON/CSV under docs/data."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import rating
from .aggregate import COMPONENT_KEYS, PBP_COLUMNS, epa_plays, regular_season, team_components
from .legacy import competition_ranks, legacy_from_components, legacy_net

SOURCE = "nflverse via nfl_data_py (https://github.com/nflverse)"
SCHEDULE_FALLBACK = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "data"

# Historical / alternate abbreviations -> abbreviations used in the pbp.
ABBR_FIX = {"LAR": "LA", "STL": "LA", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "JAC": "JAX"}


def norm_abbr(abbr):
    """Normalize a team abbreviation to the form used in nflverse pbp."""
    return ABBR_FIX.get(abbr, abbr)


def download_pbp(season: int) -> pd.DataFrame:
    """Download one season of play-by-play via nfl_data_py (empty if unavailable)."""
    import nfl_data_py as nfl

    for cols in (PBP_COLUMNS, None):
        try:
            kwargs = {"columns": cols} if cols else {}
            df = nfl.import_pbp_data([season], include_participation=False, downcast=True, cache=False, **kwargs)
            return df
        except Exception as exc:  # noqa: BLE001 - missing column or missing season
            print(f"pbp import ({'filtered' if cols else 'all columns'}) failed for {season}: {exc}")
    return pd.DataFrame()


def download_schedule(season: int) -> pd.DataFrame:
    """Download the schedule, falling back to the nflverse release CSV."""
    import nfl_data_py as nfl

    try:
        sched = nfl.import_schedules([season])
    except Exception as exc:  # noqa: BLE001
        print(f"import_schedules failed ({exc}); using nflverse release fallback")
        sched = pd.read_csv(SCHEDULE_FALLBACK)
        sched = sched[sched["season"] == season]
    return sched


def download_teams() -> pd.DataFrame:
    """Download team metadata from nfl_data_py."""
    import nfl_data_py as nfl

    return nfl.import_team_desc()


def records(sched: pd.DataFrame) -> pd.DataFrame:
    """Wins, losses, ties and point differential from played REG games."""
    g = sched[(sched["game_type"] == "REG") & sched["home_score"].notna() & sched["away_score"].notna()]
    rows = {}
    for _, r in g.iterrows():
        for team, pf, pa in ((r["home_team"], r["home_score"], r["away_score"]),
                             (r["away_team"], r["away_score"], r["home_score"])):
            t = norm_abbr(team)
            d = rows.setdefault(t, {"wins": 0, "losses": 0, "ties": 0, "point_diff": 0})
            d["wins"] += int(pf > pa)
            d["losses"] += int(pf < pa)
            d["ties"] += int(pf == pa)
            d["point_diff"] += int(pf - pa)
    return pd.DataFrame.from_dict(rows, orient="index")


def _clean(x, nd=6):
    """Round a float, raising if it is not finite."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("non-finite value in output")
    return round(x, nd)


def build_teams(pbp: pd.DataFrame, sched: pd.DataFrame, team_desc: pd.DataFrame) -> list[dict]:
    """Combine components, legacy and v2 ratings, metadata and records."""
    comps = team_components(pbp)
    adj = rating.adjust(epa_plays(pbp))
    rec = records(sched)
    desc = team_desc.copy()
    desc["abbr"] = desc["team_abbr"].map(norm_abbr)
    desc = desc.drop_duplicates("abbr", keep="first").set_index("abbr")

    teams = sorted(comps)
    rows = []
    for t in teams:
        off_f = legacy_from_components(comps[t]["offense"])
        def_f = legacy_from_components(comps[t]["defense"])
        meta = desc.loc[t] if t in desc.index else None
        r = rec.loc[t] if t in rec.index else {"wins": 0, "losses": 0, "ties": 0, "point_diff": 0}
        rows.append({
            "team": t,
            "name": str(meta["team_name"]) if meta is not None else t,
            "conference": str(meta["team_conf"]) if meta is not None else "",
            "division": str(meta["team_division"]) if meta is not None else "",
            "wins": int(r["wins"]), "losses": int(r["losses"]), "ties": int(r["ties"]),
            "point_diff": int(r["point_diff"]),
            "v2": _clean(adj.loc[t, "v2"]),
            "off_epa": _clean(adj.loc[t, "off_epa"]), "def_epa": _clean(adj.loc[t, "def_epa"]),
            "off_epa_adj": _clean(adj.loc[t, "off_epa_adj"]), "def_epa_adj": _clean(adj.loc[t, "def_epa_adj"]),
            "legacy": _clean(legacy_net(off_f, def_f), 4),
            "off_function": _clean(off_f, 4), "def_function": _clean(def_f, 4),
            "components": {
                side: {k: (v if k in ("plays", "drives") else _clean(v, 6)) for k, v in comps[t][side].items()}
                for side in ("offense", "defense")
            },
        })
    for key, field, hib in (("v2_rank", "v2", True), ("legacy_rank", "legacy", True),
                            ("off_function_rank", "off_function", True),
                            ("def_function_rank", "def_function", False)):
        for row, rk in zip(rows, competition_ranks([r[field] for r in rows], hib)):
            row[key] = rk
    rows.sort(key=lambda r: (r["v2_rank"], r["team"]))
    return rows


def flat_row(t: dict) -> dict:
    """Flatten a team object for CSV output."""
    flat = {k: v for k, v in t.items() if k != "components"}
    for side, pre in (("offense", "off_"), ("defense", "def_")):
        for k in COMPONENT_KEYS:
            flat[pre + k] = t["components"][side][k]
    return flat


def build_season(season: int):
    """Build one season; return (payload dict, teams) or None if no REG plays."""
    pbp = download_pbp(season)
    if pbp.empty:
        return None
    reg = regular_season(pbp)
    if reg.empty or not reg["play_type"].isin(["pass", "run"]).any():
        return None
    sched = download_schedule(season)
    teams = build_teams(pbp, sched, download_teams())
    weeks = pd.to_numeric(reg["week"], errors="coerce").dropna()
    played = sched[(sched["game_type"] == "REG") & sched["home_score"].notna()]
    payload = {
        "season": season,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "week_min": int(weeks.min()), "week_max": int(weeks.max()),
        "games_played": int(len(played)),
        "teams": teams,
    }
    return payload


def write_season(payload: dict, out_dir: Path) -> None:
    """Write {season}.json and {season}.csv and refresh index.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    season = payload["season"]
    (out_dir / f"{season}.json").write_text(json.dumps(payload, indent=1) + "\n")
    pd.DataFrame([flat_row(t) for t in payload["teams"]]).to_csv(out_dir / f"{season}.csv", index=False)
    idx_path = out_dir / "index.json"
    seasons = set()
    if idx_path.exists():
        seasons = set(json.loads(idx_path.read_text()).get("seasons", []))
    seasons.add(season)
    seasons = sorted(seasons, reverse=True)
    index = {
        "seasons": seasons,
        "default_season": seasons[0],
        "generated_at": payload["generated_at"],
        "source": SOURCE,
    }
    idx_path.write_text(json.dumps(index, indent=1) + "\n")


def run(season: str, out_dir: Path = DEFAULT_OUT) -> int:
    """Build ``season`` (an int string or 'latest'); return the season written."""
    if season == "latest":
        year = datetime.now(timezone.utc).year
        candidates = [year, year - 1]
    else:
        candidates = [int(season)]
    for y in candidates:
        payload = build_season(y)
        if payload is not None:
            write_season(payload, out_dir)
            print(f"wrote season {y}: {len(payload['teams'])} teams")
            return y
        print(f"no regular-season plays for {y}")
    raise SystemExit(f"no data available for {season}")
