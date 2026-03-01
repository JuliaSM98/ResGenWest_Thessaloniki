from dataclasses import dataclass
from typing import Tuple


@dataclass
class Params:
    # RES intensities (per m2)
    cost_res: float = 240.0
    co2_res: float = 71.0
    # NBS intensities (per tree)
    cost_nbs: float = 600.0
    co2_nbs: float = 25.0
    # Coverage (percent 0..100).
    # pct_covered_by_NBS_RES is the legacy single value used as fallback.
    # pct_covered_roof / pct_covered_ground override it per cell type when >= 0.
    pct_covered_by_NBS_RES: float = 50.0
    pct_covered_roof: float = -1.0    # if < 0, falls back to pct_covered_by_NBS_RES
    pct_covered_ground: float = -1.0  # if < 0, falls back to pct_covered_by_NBS_RES
    # Tree layout
    tree_cover_area: float = 5.0          # m2 per tree footprint
    # PV layout
    res_cell_area: float = 5.0            # m2 per PV unit
    # Roof structural constraints
    tree_weight: float = 400.0            # kg per tree (approx.)
    max_roof_load: float = 100.0          # kg per m2 maximum allowable load
    # Economies of scale (floors in [0..1], thresholds in units)
    res_cost_floor: float = 1.0
    nbs_cost_floor: float = 1.0
    res_discount_units: float = 1e30
    nbs_discount_units: float = 1e30


def coverage_for_type(p: Params, cell_type: str) -> float:
    """Return coverage fraction (0..1) for the given cell type."""
    ct = (cell_type or "").strip().lower()
    if ct == "roof" and p.pct_covered_roof >= 0:
        return max(0.0, min(100.0, p.pct_covered_roof)) / 100.0
    if ct == "ground" and p.pct_covered_ground >= 0:
        return max(0.0, min(100.0, p.pct_covered_ground)) / 100.0
    return max(0.0, min(100.0, p.pct_covered_by_NBS_RES)) / 100.0


def compute_block_option_metrics(area_m2: float, res_pct: float, nbs_pct: float, cell_type: str, p: Params) -> Tuple[float, float]:
    """Return (cost, co2) for a single block given its area and an option.

    covered_area = area_m2 * coverage_for_type(p, cell_type)
    RES area     = covered_area * res_pct
    NBS area     = covered_area * nbs_pct  → integer trees
    """
    cov = coverage_for_type(p, cell_type)
    res_area = max(0.0, area_m2 * cov * max(0.0, res_pct))
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
