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


def build_model(block_opts: Sequence[Sequence[IntPoint]]):
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

    return model, x_vars, cost_expr, co2_expr


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


def solve_max_co2_under_budget(block_opts: Sequence[Sequence[IntPoint]], budget_int: int):
    """Maximize CO2 under a budget constraint (single-phase, no tie-breaking)."""
    model, x, cost_expr, co2_expr = build_model(block_opts)
    model.Add(cost_expr <= budget_int)
    model.Maximize(co2_expr)
    return _solve(model, x, cost_expr, co2_expr)


def solve_min_cost_above_co2(block_opts: Sequence[Sequence[IntPoint]], co2_int_target: int):
    """Minimize cost subject to CO2 >= co2_int_target."""
    model, x, cost_expr, co2_expr = build_model(block_opts)
    model.Add(co2_expr >= co2_int_target)
    model.Minimize(cost_expr)
    return _solve(model, x, cost_expr, co2_expr)


def solve_both_constraints(block_opts: Sequence[Sequence[IntPoint]], budget_int: int, co2_int_target: int):
    """Maximize CO2 subject to cost <= budget_int and CO2 >= co2_int_target."""
    model, x, cost_expr, co2_expr = build_model(block_opts)
    model.Add(cost_expr <= budget_int)
    model.Add(co2_expr >= co2_int_target)
    model.Maximize(co2_expr)
    return _solve(model, x, cost_expr, co2_expr)

def frontier_by_budget_steps(block_opts: Sequence[Sequence[IntPoint]], min_budget: int, max_budget: int, steps: int):
    """Compute frontier by sampling budgets uniformly in [min_budget, max_budget]."""
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
    return out