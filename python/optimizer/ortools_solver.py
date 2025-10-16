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


def solve_max_co2_under_budget(block_opts: Sequence[Sequence[IntPoint]], budget_int: int):
    model, x_vars, cost_expr, co2_expr = build_model(block_opts, budget_int=budget_int)
    model.Maximize(co2_expr)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0  # adjustable
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    # Extract selection
    selection: List[int] = []
    for b, xb in enumerate(x_vars):
        idx = 0
        for o, x in enumerate(xb):
            if solver.Value(x) == 1:
                idx = o
                break
        selection.append(idx)
    total_cost = solver.Value(cost_expr)
    total_co2 = solver.Value(co2_expr)
    return total_cost, total_co2, selection


def frontier_by_budget_tight(block_opts: Sequence[Sequence[IntPoint]], max_budget: int):
    """Enumerate the frontier by tightening budget to the best solution's cost-1 until infeasible.

    Returns a list of tuples (cost_int, co2_int, selection).
    """

    results: List[Tuple[int, int, List[int]]] = []
    current_budget = max_budget
    seen = set()
    while current_budget >= 0:
        res = solve_max_co2_under_budget(block_opts, current_budget)
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
    # Sort by cost asc
    results.sort(key=lambda t: t[0])
    return results


def frontier_by_budget_steps(block_opts: Sequence[Sequence[IntPoint]], min_budget: int, max_budget: int, steps: int):
    """Compute frontier by sampling budgets uniformly between [min_budget, max_budget]."""
    if steps <= 1:
        steps = 2
    budgets = [int(round(min_budget + i * (max_budget - min_budget) / (steps - 1))) for i in range(steps)]
    seen = set()
    out: List[Tuple[int, int, List[int]]] = []
    for B in budgets:
        res = solve_max_co2_under_budget(block_opts, B)
        if res is None:
            continue
        c, z, sel = res
        if (c, z) not in seen:
            seen.add((c, z))
            out.append((c, z, sel))
    out.sort(key=lambda t: t[0])
    return out

