# NFL Rankings

A free, College Football Index-style NFL rankings site. A Python pipeline pulls
[nflverse](https://github.com/nflverse) data and writes static JSON/CSV; a
vanilla HTML/CSS/JS site in `docs/` renders it. No build step, no paid sports
APIs, no scraping of Pro Football Reference.

## Two models

**v2 (default): schedule-adjusted EPA margin.** Play-weighted EPA/play for each
offense and defense on regular-season scrimmage plays, opponent-adjusted over 20
iterations and re-centered. `v2 = adj_off - adj_def`; higher is better. It is not
DVOA and not a betting model. See `docs/methodology.html`.

**Legacy v1 FUNCTION (secondary toggle).** Chris Robinson's original
spreadsheet formula:

```
FUNCTION = ((pts_per_drive * (fg_pct + xp_pct))
            + (yards_per_play * (first_down_pct + third_down_rate)))
           * (score_pct + (100 - turnover_pct))
net = offense FUNCTION - defense FUNCTION   # higher is better
```

### Column correction

The notes extracted from the workbook say "FGA+FGM" and "EXP". Those labels are
wrong. The cells reproduce every 2022 FUNCTION value (max abs error ~1e-10) only
with **FG% + XP%** (kicking, Numbers columns Q and T) and the calculated
**1stD%** (Numbers column AC). EXP is unused. v1 follows the cells Chris actually
sorted by, not the prose.

Scales are kept as stored in the workbook: `fg_pct`, `xp_pct` and
`third_down_rate` (3D%) are fractions (0.415); `first_down_pct`, `score_pct` and
`turnover_pct` are percentage points (30.91).

### nflverse approximations for live seasons

Regular season only (`season_type == "REG"`). Defense = same stats over plays
and drives where the team is the defense.

- Scrimmage plays: `play_type` pass/run, excluding no-plays, null `posteam` and
  two-point attempts.
- `yards_per_play`: yards gained / scrimmage plays.
- `first_down_pct`: 100 * (pass + rush + penalty first downs) / plays; falls back
  to `first_down` if those columns are missing.
- `third_down_rate`: converted / (converted + failed), a fraction, 0 if none.
- `fg_pct`, `xp_pct`: made / attempts, fractions, 0 if none.
- Drive: `(game_id, posteam, fixed_drive)`, kickoffs and null drive ids ignored.
- `score_pct`: drives with an offensive TD or made FG / drives. nflverse's
  `drive_ended_with_score` also flags defensive scores (pick-sixes, safeties), so
  it is only honored when `fixed_drive_result` is Touchdown or Field goal.
- `turnover_pct`: drives with an offensive interception or lost fumble (play-level
  `interception` / `fumble_lost` on scrimmage plays) / drives.
- `pts_per_drive`: 6/offensive TD + 3/FG + 1/XP + 2/two-point conversion, over
  drives. Defensive scores are excluded.

nflverse-derived legacy numbers will **not** exactly match the 2022 PFR paste;
the fixture test locks the formula itself, not the inputs.

## Data

Free data only: [nflverse](https://github.com/nflverse) (play-by-play, schedules,
team metadata) via `nfl_data_py`. Thanks to the nflverse project.

## Local setup

Python 3.12. `nfl_data_py` 0.3.3 declares `pandas<2` and will not build on 3.12,
so it is installed with `--no-deps` after the other requirements:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install --no-deps nfl_data_py==0.3.3
scripts/refresh.sh latest          # or: python -m nflrankings --season 2022
```

`--season latest` uses the current UTC year and falls back to the previous year if
there are no regular-season plays yet. Output goes to `docs/data/{season}.json`,
`{season}.csv` and `index.json`. Preview with `python -m http.server -d docs`.

## GitHub Pages

Settings → Pages → Deploy from branch → `main` → `/docs`.

## Weekly refresh

`.github/workflows/refresh.yml` runs Tuesdays at 14:00 UTC (after Monday Night
Football), or manually with an optional `season` input, and commits changes under
`docs/data` as "Refresh NFL rankings".

## Tests

```bash
pytest -q
```

Tests run offline: the 2022 workbook fixtures (`tests/fixtures/nfl2022/*.csv`)
lock the legacy formula, and small synthetic frames cover aggregation and the v2
rating.
