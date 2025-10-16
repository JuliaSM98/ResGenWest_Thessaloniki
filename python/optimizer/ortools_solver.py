from dataclasses import dataclass
from typing import List, Sequence, Tuple, Optional

from ortools.sat.python import cp_model


IntPoint = Tuple[int, int]  # (cost_int, co2_int)


@dataclass
class Scale: # For decimal precision in the optomizer
    cost: int = 1   # euros -> euros, with 100 euros ->cents
    co2: int = 1    # kg -> kg, with 100 kg -> 0.01 kg units


def scale_points(points: Sequence[Tuple[float, float]], scale: Scale) -> List[IntPoint]:
    out: List[IntPoint] = []
    for c, z in points:
        ci = int(round(c * scale.cost))
        zi = int(round(z * scale.co2))
        out.append((ci, zi))
    return out


def build_model(block_opts: Sequence[Sequence[IntPoint]], budget_int: Optional[int] = None):
    """Build a CP-SAT model for selecting exactly one option per block.

    - block_opts: per-block options as (cost_int, co2_int)
    - budget_int: if provided, adds constraint total_cost <= budget_int
    Returns (model, x_vars, cost_expr, co2_expr).
    """
    model = cp_model.CpModel()
    x_vars: List[List[cp_model.IntVar]] = []

    # Decision vars and per-block exactly-one constraints
    for b, opts in enumerate(block_opts):
        xb: List[cp_model.IntVar] = []
        for o, _ in enumerate(opts):
            xb.append(model.NewBoolVar(f"x_b{b}_o{o}"))
        model.Add(sum(xb) == 1)
        x_vars.append(xb)
   
    # Totals
    cost_terms = []
    co2_terms = []
    for b, opts in enumerate(block_opts):
        for o, (c_int, z_int) in enumerate(opts):
            x = x_vars[b][o]
            cost_terms.append(c_int * x)
            co2_terms.append(z_int * x)
    cost_expr = sum(cost_terms)
    co2_expr = sum(co2_terms)

    if budget_int is not None:
        model.Add(cost_expr <= budget_int)

    return model, x_vars, cost_expr, co2_expr


def prune_points(points: List[Tuple[int, int, List[int]]]) -> List[Tuple[int, int, List[int]]]:
    """Sort by cost asc and drop dominated points (keep strictly increasing CO2)."""
    if not points:
        return points
    points.sort(key=lambda t: t[0])
    pruned: List[Tuple[int, int, List[int]]] = []
    best_co2 = -10**18
    for c, z, sel in points:
        if z > best_co2:
            pruned.append((c, z, sel))
            best_co2 = z
    return pruned


def _solve(model: cp_model.CpModel, x_vars: Sequence[Sequence[cp_model.IntVar]], cost_expr, co2_expr):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0  # adjustable
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    selection: List[int] = []
    for xb in x_vars:
        idx = 0
        for o, x in enumerate(xb):
            if solver.Value(x) == 1:
                idx = o
                break
        selection.append(idx)
    return solver.Value(cost_expr), solver.Value(co2_expr), selection


def solve_max_co2_under_budget(block_opts: Sequence[Sequence[IntPoint]], budget_int: int, refine_lexicographic: bool = False):
    """Maximize CO2 under budget. If refine_lexicographic=True, also minimize cost among max-CO2 solutions."""
    # Step 1: maximize CO2
    model1, x1, cost1, co21 = build_model(block_opts, budget_int=budget_int)
    model1.Maximize(co21)
    res1 = _solve(model1, x1, cost1, co21)
    if res1 is None:
        return None
    if not refine_lexicographic:
        return res1
    _c1, z1, _sel1 = res1
    # Step 2: minimize cost subject to CO2 == z1 and cost<=budget
    model2, x2, cost2, co22 = build_model(block_opts, budget_int=budget_int)
    model2.Add(co22 == z1)
    model2.Minimize(cost2)
    res2 = _solve(model2, x2, cost2, co22)
    return res2


def frontier_by_budget_tight(block_opts: Sequence[Sequence[IntPoint]], max_budget: int, *, refine_lexicographic: bool = False, prune: bool = False):
    """Enumerate the frontier by tightening budget to the best solution's cost-1 until infeasible.

    Returns a list of tuples (cost_int, co2_int, selection).
    """

    results: List[Tuple[int, int, List[int]]] = []
    current_budget = max_budget
    seen = set()
    while current_budget >= 0:
        res = solve_max_co2_under_budget(block_opts, current_budget, refine_lexicographic=refine_lexicographic)
        if res is None:
            break
        c, z, sel = res
        key = (c, z)
        if key not in seen:
            seen.add(key)
            results.append((c, z, sel))
        # Tighten budget just below achieved cost to explore new points
        next_budget = c - 1
        if next_budget < 0 or next_budget >= current_budget:
            break
        current_budget = next_budget
    return prune_points(results) if prune else results


def frontier_by_budget_steps(block_opts: Sequence[Sequence[IntPoint]], min_budget: int, max_budget: int, steps: int, *, refine_lexicographic: bool = False, prune: bool = False):
    """Compute frontier by sampling budgets uniformly between [min_budget, max_budget]."""
    if steps <= 1:
        steps = 2
    budgets = [int(round(min_budget + i * (max_budget - min_budget) / (steps - 1))) for i in range(steps)]
    seen = set()
    out: List[Tuple[int, int, List[int]]] = []
    for B in budgets:
        res = solve_max_co2_under_budget(block_opts, B, refine_lexicographic=refine_lexicographic)
        if res is None:
            continue
        c, z, sel = res
        if (c, z) not in seen:
            seen.add((c, z))
            out.append((c, z, sel))
    return prune_points(out) if prune else out
