"""The v1 FUNCTION ranking is gone from the tree that ships."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {Path("tests/test_no_legacy.py")}
TEXT_SUFFIXES = {".py", ".md", ".html", ".js", ".css", ".json", ".csv", ".yml", ".yaml", ".txt", ".sh"}


def test_legacy_fixtures_are_gone():
    assert not (ROOT / "nflrankings" / "legacy.py").exists()
    assert not (ROOT / "tests" / "fixtures").exists()
    assert not (ROOT / "tests" / "test_legacy_2022.py").exists()


def test_no_legacy_ranking_strings():
    needles = (
        "legacy_function",
        "legacy_from_components",
        "legacy_net",
        "legacy_rank",
        "off_function",
        "def_function",
        "Legacy FUNCTION",
        "legacy FUNCTION",
        "v1 FUNCTION",
    )
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if rel in SKIP:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            if needle in text:
                hits.append(f"{rel}: {needle}")
        if "legacy" in text.lower():
            hits.append(f"{rel}: legacy")
    assert hits == []
