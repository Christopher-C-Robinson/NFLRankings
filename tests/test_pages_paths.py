"""Project Pages URLs stay root-absolute, and a failed fetch cannot leave Loading."""

import re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = "https://christopher-c-robinson.github.io/NFLRankings"
ASSET = re.compile(r"""(?:href|src)=["'](?!https:|data:|#|/)[^"']+["']""")


def test_no_slash_document_url_drops_relative_assets():
    """The bug: a project URL without a trailing slash resolves relatives on the host."""
    bare = PAGES  # no trailing slash
    assert urljoin(bare, "assets/app.css") == "https://christopher-c-robinson.github.io/assets/app.css"
    assert urljoin(bare, "data/index.json") == "https://christopher-c-robinson.github.io/data/index.json"
    assert urljoin(bare, "/NFLRankings/assets/app.css") == PAGES + "/assets/app.css"
    assert urljoin(PAGES + "/", "/NFLRankings/data/index.json") == PAGES + "/data/index.json"


def test_html_uses_project_root_for_local_urls():
    pages = list(DOCS.glob("*.html"))
    assert pages
    for path in pages:
        text = path.read_text()
        match = ASSET.search(text)
        assert match is None, f"{path.name} still has a relative URL: {match.group(0)}"
        assert 'href="/NFLRankings/assets/app.css"' in text
        assert 'src="/NFLRankings/assets/theme.js"' in text
        assert 'href="#main"' in text
    index = (DOCS / "index.html").read_text()
    assert 'src="/NFLRankings/assets/site.js"' in index
    assert 'src="/NFLRankings/assets/app.js"' in index
    assert "Hard-refresh" in index


PRESENTATION = {"chart-colors.js", "game-cards.js", "season-outlook.js"}


def test_scripts_fetch_through_the_project_root():
    site = (DOCS / "assets" / "site.js").read_text()
    assert 'var ROOT = "/NFLRankings/"' in site
    assert "timed out after 8s" in site
    assert "fetch(url" in site
    for path in (DOCS / "assets").glob("*.js"):
        text = path.read_text()
        assert "fetch(" not in text or path.name == "site.js", path.name
        assert 'textContent = "Loading' not in text
        if path.name in ("site.js", "theme.js", "model.js") or path.name in PRESENTATION:
            continue
        assert 'site.data("index.json")' in text
        assert "NFLSite" in text


def test_cfi_port_uses_project_root_assets():
    week = (DOCS / "week.html").read_text()
    team = (DOCS / "team.html").read_text()
    assert 'href="/NFLRankings/assets/cfi-ui.css"' in week
    assert 'src="/NFLRankings/assets/chart-colors.js"' in week
    assert 'src="/NFLRankings/assets/game-cards.js"' in week
    assert 'id="games-content"' in week
    assert "<tbody id=\"rows\">" not in week
    assert 'href="/NFLRankings/assets/cfi-ui.css"' in team
    assert 'src="/NFLRankings/assets/season-outlook.js"' in team
    cards = (DOCS / "assets" / "game-cards.js").read_text()
    outlook = (DOCS / "assets" / "season-outlook.js").read_text()
    assert "game-day-probability" in cards
    assert "pregame" in cards.lower()
    assert "season-chart-bar" in outlook
    assert "weeks[].v2" in outlook
    app = (DOCS / "assets" / "app.js").read_text()
    assert '$("export").' not in app
    assert "if (exp)" in app
    assert "Could not load rankings" in app


def test_skip_link_is_clipped_not_only_shifted():
    css = (DOCS / "assets" / "app.css").read_text()
    assert "top: -48px" not in css
    rule = css.split(".skip-link:focus", 1)[0]
    skip = rule.split(".skip-link {", 1)[1]
    assert "width: 1px" in skip
    assert "height: 1px" in skip
    assert "overflow: hidden" in skip
    assert "clip:" in skip
    assert "clip-path:" in skip
    focus = css.split(".skip-link:focus", 1)[1].split("}", 1)[0]
    assert "clip: auto" in focus
    assert "width: auto" in focus
