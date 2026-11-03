"""Accuracy stays on 2026, and the week page states the Wednesday rule."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_accuracy_page_has_no_season_picker():
    html = (DOCS / "accuracy.html").read_text()
    script = (DOCS / "assets" / "accuracy.js").read_text()
    assert 'id="season"' not in html
    assert "<select" not in html
    assert "2026" in html
    assert "does not switch seasons" in html
    assert "CURRENT_SEASON = 2026" in script
    assert "onchange" not in script
    assert 'site.data("index.json")' in script
    assert 'site.data(season + ".json")' in script or "CURRENT_SEASON" in script


def test_week_page_uses_the_unplayed_week_and_wednesday_boundary():
    html = (DOCS / "week.html").read_text()
    script = (DOCS / "assets" / "week.js").read_text()
    assert 'id="week-note"' in html
    assert "Wednesday" in html
    assert "current_week" in script
    assert "unplayed" in script
    assert "wednesday-tuesday" in script
    assert "nflverse week number" in script
    assert "footballWeekWindow" in script


def test_power_is_on_the_board_team_page_and_matchup():
    index = (DOCS / "index.html").read_text()
    app = (DOCS / "assets" / "app.js").read_text()
    team = (DOCS / "assets" / "team.js").read_text()
    matchup = (DOCS / "assets" / "matchup.js").read_text()
    method = (DOCS / "methodology.html").read_text()
    assert 'id="power-panel"' in index
    assert "renderPower" in app
    assert "division_power" in app
    assert "Division and conference" in team
    assert "Division / conference adjustment" in matchup
    assert "0.5 team" in method
    assert "Wednesday" in method
    assert "win_chance_rank" in app
