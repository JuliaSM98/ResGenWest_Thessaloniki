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
    pct_covered_by_NBS_RES: float = 50.0  # percent 0..100
    tree_cover_area: float = 5.0          # m2 per tree footprint
    # Roof structural constraints
    tree_weight: float = 400.0            # kg per tree (approx.)
    max_roof_load: float = 100.0          # kg per m2 maximum allowable load


def compute_block_option_metrics(area_m2: float, res_pct: float, nbs_pct: float, cell_type: str, p: Params) -> Tuple[float, float]:
    """Return (cost, co2) for a single block given its area and an option.

    The coverage parameter applies to the whole area for both RES and NBS:
    - covered_area = area_m2 * coverage, coverage = clamp(pct_covered_by_NBS_RES, 0..100)/100
    - RES area      = covered_area * res_pct
    - effective NBS area = covered_area * nbs_pct
    - trees = floor(effective NBS area / tree_cover_area)
    """
    cov = max(0.0, min(100.0, p.pct_covered_by_NBS_RES)) / 100.0
    res_area = max(0.0, area_m2 * cov * max(0.0, res_pct))
    # integer trees as in NetLogo
    eff_nbs_area = max(0.0, area_m2 * cov * max(0.0, nbs_pct))
    trees = int(eff_nbs_area // max(1e-9, p.tree_cover_area))
    # Roof load cap: trees <= floor(eff_nbs_area * max_roof_load / tree_weight)
    if (cell_type or "").lower() == "roof" and p.tree_weight > 0:
        load_cap = int((eff_nbs_area * p.max_roof_load) // p.tree_weight)
        if trees > load_cap:
            trees = load_cap

    res_cost = res_area * p.cost_res
    res_co2 = res_area * p.co2_res
    nbs_cost = trees * p.cost_nbs
    nbs_co2 = trees * p.co2_nbs

    return (res_cost + nbs_cost, res_co2 + nbs_co2)

