# NFL Rankings

A free, College Football Index-style NFL rankings site. A Python pipeline pulls
[nflverse](https://github.com/nflverse) data and writes static JSON/CSV; a
vanilla HTML/CSS/JS site in `docs/` renders it. No build step, no paid sports
APIs, no scraping of Pro Football Reference.

**Live site:** [NFL Rankings](https://christopher-c-robinson.github.io/NFLRankings/)

## The ranking

Teams are ranked by **average neutral-site win chance against the other 31
teams**. That is the same kind of summary College Football Index uses: one
shared hypothetical schedule, not a weighted blend, and not a team's actual
record.

Underneath, strength is still the **v2 schedule-adjusted EPA margin**
(`adj_off − adj_def` on regular-season scrimmage plays). A fitted conversion
turns an EPA gap into a point spread and a logistic win chance. Home field is
fit from nflverse final scores and is **not** added inside the ranking, so a
venue does not move a team up the board. The v2 EPA margin stays on the board
as a supporting column. Because the conversion is strictly increasing, the
win-chance order matches the EPA order. The percentage is still the average of
the matchup chances, which is not the chance of beating an average team.

Filters for conference, division, and team name hide rows. They do not
renumber ranks. See `docs/methodology.html` and `nflrankings/conversion.json`
for the fit window, the home-field estimate, and the assumptions.

The weekly refresh applies the shipped conversion. It does not refit it.
Refit with:

```bash
python -m nflrankings.fit_history --first 2016 --last 2025
```

The matchup page (`docs/matchup.html`) projects one game: spread, win chance,
score, and an 80% margin range from the fitted residual. Pass and rush EPA are
shown and are not added into the spread. Team pages (`docs/team.html`) list the
schedule, expected wins, a projected record, and the season EPA chart. Those
schedule projections use the current season rating. The week board and the
accuracy page use a separate frozen pregame rating from earlier weeks, blended with the previous season while that sample is thin.
Drive starting field position, special-teams EPA, success rate, and explosiveness were screened on earlier seasons and are not in that spread. `python scripts/screen_advanced.py` replays that screen. A later screen fits a rolling ridge on the rest of the open file — pass and rush, downs, drives, special teams, rest, travel, weather, the quarterback, and players ruled out — with weights that change by season. It did not beat this spread on both 2024 and 2025, so the spread is unchanged. `python scripts/screen_aspects.py` replays it.
Final scores are nflverse results. A live score feed is not wired up.

## Data

Free data only: [nflverse](https://github.com/nflverse) play-by-play, schedules,
and team metadata (including logos and colors) via `nfl_data_py`. Thanks to
the nflverse project.

## Local setup

Python 3.12. `nfl_data_py` 0.3.3 declares `pandas<2` and will not build on 3.12,
so it is installed with `--no-deps` after the other requirements:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install --no-deps nfl_data_py==0.3.3
scripts/refresh.sh latest          # or: python -m nflrankings --season 2025
```

`--season latest` uses the current UTC year and falls back to the previous year if
there are no regular-season plays yet. Output goes to `docs/data/{season}.json`,
`{season}.csv` and `index.json`. Seasons before 2025 are not written there and
do not appear on the site. Pass `--out` to keep an older backfill in another
directory. 2022 is not a public season. Styles, scripts, and JSON use root-absolute
`/NFLRankings/...` URLs, the same path GitHub project Pages serves. Preview
under that prefix:

```bash
mkdir -p /tmp/nfl-preview
ln -sfn "$PWD/docs" /tmp/nfl-preview/NFLRankings
python -m http.server -d /tmp/nfl-preview 8000
```

Open http://127.0.0.1:8000/NFLRankings/ . A URL without the trailing slash
should load the same board.

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

Tests run offline. They cover the win-chance math, the margin and logistic fits,
scrimmage-play filters, the team build, and a scan that the old FUNCTION ranking
is gone.
