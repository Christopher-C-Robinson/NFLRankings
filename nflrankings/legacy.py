"""Legacy v1 FUNCTION formula, net score and ranks. No I/O.

The formula follows the cells of the 2022 NFL2022.numbers workbook, not the
prose labels in the extract notes (see README for the column correction)::

    ((pts_per_drive * (fg_pct + xp_pct))
     + (yards_per_play * (first_down_pct + third_down_rate)))
    * (score_pct + (100 - turnover_pct))

Scales are kept exactly as stored in the workbook: ``fg_pct``, ``xp_pct`` and
``third_down_rate`` are fractions; ``first_down_pct``, ``score_pct`` and
``turnover_pct`` are percentage points.
"""

from __future__ import annotations

from typing import Mapping, Sequence


def legacy_function(
    pts_per_drive: float,
    fg_pct: float,
    xp_pct: float,
    yards_per_play: float,
    first_down_pct: float,
    third_down_rate: float,
    score_pct: float,
    turnover_pct: float,
) -> float:
    """Return the legacy FUNCTION value for one offense or one defense."""
    kicking = pts_per_drive * (fg_pct + xp_pct)
    moving = yards_per_play * (first_down_pct + third_down_rate)
    return (kicking + moving) * (score_pct + (100.0 - turnover_pct))


def legacy_from_components(c: Mapping[str, float]) -> float:
    """Compute legacy FUNCTION from a components mapping."""
    return legacy_function(
        c["pts_per_drive"],
        c["fg_pct"],
        c["xp_pct"],
        c["yards_per_play"],
        c["first_down_pct"],
        c["third_down_rate"],
        c["score_pct"],
        c["turnover_pct"],
    )


def legacy_net(off_function: float, def_function: float) -> float:
    """Net FUNCTION: offense minus defense. Higher is better."""
    return off_function - def_function


def competition_ranks(values: Sequence[float], higher_is_better: bool = True) -> list[int]:
    """Competition ("min") ranks: ties share the best rank, 1 = best."""
    keyed = [round(float(v), 9) for v in values]
    ranks = []
    for k in keyed:
        if higher_is_better:
            better = sum(1 for o in keyed if o > k)
        else:
            better = sum(1 for o in keyed if o < k)
        ranks.append(better + 1)
    return ranks
