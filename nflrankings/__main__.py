"""CLI: python -m nflrankings --season 2022|latest."""

import argparse
from pathlib import Path

from .pipeline import DEFAULT_OUT, run


def main() -> None:
    """Parse arguments and run the pipeline."""
    p = argparse.ArgumentParser(prog="nflrankings", description="Build NFL rankings from nflverse data.")
    p.add_argument("--season", default="latest", help="season year or 'latest'")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output directory (default docs/data)")
    a = p.parse_args()
    run(a.season, Path(a.out))


if __name__ == "__main__":
    main()
