from dataclasses import dataclass
from typing import Tuple


@dataclass
class Params:
    # RES intensities (per m2)
    cost_res: float = 240.0
    co2_res: float = 48.0
    # NBS intensities (per tree)
    cost_nbs: float = 600.0
    co2_nbs: float = 25.0
    # Tree layout
    pct_covered_by_trees: float = 50.0  # percent 0..100
    tree_cover_area: float = 5.0        # m2 per tree


def compute_block_option_metrics(area_m2: float, res_pct: float, nbs_pct: float, p: Params) -> Tuple[float, float]:
    """Return (cost, co2) for a single block given its area and an option.

    - area allocated to RES = area_m2 * res_pct
    - effective NBS area = area_m2 * (pct_covered_by_trees/100) * nbs_pct
    - trees = floor(effective NBS area / tree_cover_area)
    """
    res_area = max(0.0, area_m2 * max(0.0, res_pct))
    # integer trees as in NetLogo
    eff_nbs_area = max(0.0, area_m2 * (max(0.0, min(100.0, p.pct_covered_by_trees)) / 100.0) * max(0.0, nbs_pct))
    trees = int(eff_nbs_area // max(1e-9, p.tree_cover_area))

    res_cost = res_area * p.cost_res
    res_co2 = res_area * p.co2_res
    nbs_cost = trees * p.cost_nbs
    nbs_co2 = trees * p.co2_nbs

    return (res_cost + nbs_cost, res_co2 + nbs_co2)

