import argparse
import json
import os
from typing import List, Sequence, Tuple, Optional

from .data import load_uncovered_blocks
from .options import load_ground_options, Options
from .model import Params, compute_block_option_metrics, coverage_for_type
from .ortools_solver import (
    Scale,
    scale_points,
    frontier_by_budget_steps,
    solve_max_co2_under_budget,
    solve_min_cost_above_co2,
    solve_both_constraints,
)


def build_block_options(blocks, options, params: Params) -> Tuple[List[List[Tuple[float, float]]], List[List[Options]]]:
    """Return per-block numeric options and the matching per-block Options lists."""
    block_opts: List[List[Tuple[float, float]]] = []
    block_opt_refs: List[List[Options]] = []
    for b in blocks:
        area = float(b['area_m2'])
        cell_type = b.get('cell_type')
        options_b = [o for o in options if o.cell_type == cell_type]
        opts = []
        for o in options_b:
            c, z = compute_block_option_metrics(area, o.res_pct, o.nbs_pct, cell_type, params)
            opts.append((c, z))
        block_opts.append(opts)
        block_opt_refs.append(options_b)
    return block_opts, block_opt_refs


def discount_factor(floor: float, n: float, N: float) -> float:
    """Economies-of-scale factor: 1 - (1 - floor) * min(n/N, 1)."""
    if N <= 0:
        return 1.0
    phi = min(max(0.0, n) / N, 1.0)
    return 1.0 - (1.0 - floor) * phi


def write_csv(out_path: str, points: Sequence[Tuple[float, float]], n_blocks: int) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('cost,co2,n_blocks\n')
        for c, z in points:
            f.write(f"{c:.6f},{z:.6f},{n_blocks}\n")


def compute_counts_for_selection(blocks, block_options: List[List[Options]], selection: Sequence[int], params: Params) -> Tuple[int, int, float]:
    """Return (n_res_units, n_trees, total_res_area_m2) for a selection."""
    total_res_area = 0.0
    total_trees = 0
    for i, choice_idx in enumerate(selection):
        b = blocks[i]
        area = float(b['area_m2'])
        cell_type = (b.get('cell_type') or '').strip().lower()
        o = block_options[i][choice_idx]
        res_pct = max(0.0, o.res_pct)
        nbs_pct = max(0.0, o.nbs_pct)
        cov = coverage_for_type(params, cell_type)
        res_area = area * cov * res_pct
        eff_nbs_area = area * cov * nbs_pct
        trees = int(eff_nbs_area // max(1e-9, params.tree_cover_area))
        if cell_type == 'roof' and params.tree_weight > 0:
            load_cap = int((eff_nbs_area * params.max_roof_load) // params.tree_weight)
            if trees > load_cap:
                trees = load_cap
        total_res_area += res_area
        total_trees += trees
    n_res_units = int(total_res_area // max(1e-9, params.res_cell_area))
    return n_res_units, total_trees, total_res_area


def write_points_with_counts(out_path: str, points: Sequence[Tuple[float, float]], counts: Sequence[Tuple], n_blocks: int, params: 'Params' = None) -> None:
    """counts entries are (n_res_units, n_trees) or (n_res_units, n_trees, total_res_area_m2)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('cost,co2,n_blocks,n_res_units,n_trees,cost_discounted\n')
        for (c, z), cnt in zip(points, counts):
            nru, nt = cnt[0], cnt[1]
            res_area = cnt[2] if len(cnt) > 2 else nru * (params.res_cell_area if params else 1.0)
            if params is not None:
                rf = discount_factor(params.res_cost_floor, float(nru), float(params.res_discount_units))
                nf = discount_factor(params.nbs_cost_floor, float(nt),  float(params.nbs_discount_units))
                # Use continuous res_area for cost base (consistent with per-block table)
                c_res_base = res_area * params.cost_res
                c_nbs_base = nt * params.cost_nbs
                cost_disc = c_res_base * rf + c_nbs_base * nf
            else:
                cost_disc = c
            f.write(f"{c:.6f},{z:.6f},{n_blocks},{nru},{nt},{cost_disc:.6f}\n")


def write_selections_csv(path: str, solution_id: int, point: Tuple[float, float], blocks, block_options: List[List[Options]], selection: Sequence[int]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('solution_id,total_cost,total_co2,block_index,block_key,area_m2,res_pct,nbs_pct\n')
        for i, choice_idx in enumerate(selection):
            b = blocks[i]
            o = block_options[i][choice_idx]
            f.write(
                f"{solution_id},{point[0]:.6f},{point[1]:.6f},{i},{b.get('block')},{float(b['area_m2']):.6f},{o.res_pct:.6f},{o.nbs_pct:.6f}\n"
            )


def write_table_csv(path: str, blocks, block_options: List[List[Options]], selection: Sequence[int], params: Params) -> None:
    """Write a detailed table with economies-of-scale applied per row via portfolio-level factors."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # First pass: compute per-row base metrics and accumulate totals/units
    rows = []
    sum_area = 0.0
    sum_trees = 0
    sum_res_area = 0.0
    sum_nbs_co2 = 0.0
    sum_res_co2 = 0.0
    sum_nbs_cost_base = 0.0
    sum_res_cost_base = 0.0
    sum_total_co2 = 0.0
    res_pct_sum = nbs_pct_sum = 0.0
    total_res_units = 0
    n = len(blocks)
    for i, choice_idx in enumerate(selection):
        b = blocks[i]
        area = float(b['area_m2'])
        cell_type = (b.get('cell_type') or '').strip().lower()
        o = block_options[i][choice_idx]
        res_pct = max(0.0, o.res_pct)
        nbs_pct = max(0.0, o.nbs_pct)
        cov = coverage_for_type(params, cell_type)
        res_area = area * cov * res_pct
        eff_nbs_area = area * cov * nbs_pct
        trees = int(eff_nbs_area // max(1e-9, params.tree_cover_area))
        if cell_type == 'roof' and params.tree_weight > 0:
            load_cap = int((eff_nbs_area * params.max_roof_load) // params.tree_weight)
            if trees > load_cap:
                trees = load_cap
        nbs_co2 = trees * params.co2_nbs
        nbs_cost0 = trees * params.cost_nbs
        res_co2 = res_area * params.co2_res
        res_cost0 = res_area * params.cost_res
        total_co2 = nbs_co2 + res_co2
        sum_area += area
        sum_trees += trees
        sum_res_area += res_area
        sum_nbs_co2 += nbs_co2
        sum_res_co2 += res_co2
        sum_nbs_cost_base += nbs_cost0
        sum_res_cost_base += res_cost0
        total_res_units += int(res_area // max(1e-9, params.res_cell_area))
        sum_total_co2 += total_co2
        res_pct_sum += (res_pct * 100.0)
        nbs_pct_sum += (nbs_pct * 100.0)
        rows.append((b.get('block'), area, res_pct, nbs_pct, trees, res_area, nbs_co2, nbs_cost0, res_co2, res_cost0, total_co2))

    # Portfolio-level discount factors
    res_factor = discount_factor(params.res_cost_floor, float(total_res_units), float(params.res_discount_units))
    nbs_factor = discount_factor(params.nbs_cost_floor, float(sum_trees), float(params.nbs_discount_units))

    with open(path, 'w') as f:
        f.write('ID, Area_m2, RES%, NBS%, # Trees, RES_m2, NBS_CO2_kg, NBS_Cost_€, RES_CO2_kg, RES_Cost_€, Total_CO2_kg, Total_Cost_€\n')
        for (block_key, area, res_pct, nbs_pct, trees, res_area, nbs_co2, nbs_cost0, res_co2, res_cost0, total_co2) in rows:
            disc_nbs_cost = nbs_cost0 * nbs_factor
            disc_res_cost = res_cost0 * res_factor
            disc_total_cost = disc_nbs_cost + disc_res_cost
            f.write(
                f"{block_key}, {area:.6f}, {res_pct*100.0:.2f}%, {nbs_pct*100.0:.2f}%, {trees}, "
                f"{res_area:.2f} m2, {nbs_co2:.2f} kg, {disc_nbs_cost:.2f} €, {res_co2:.2f} kg, {disc_res_cost:.2f} €, {total_co2:.2f} kg, {disc_total_cost:.2f} €\n"
            )
        avg_res_pct = (res_pct_sum / n) if n > 0 else 0.0
        avg_nbs_pct = (nbs_pct_sum / n) if n > 0 else 0.0
        disc_nbs_total = sum_nbs_cost_base * nbs_factor
        disc_res_total = sum_res_cost_base * res_factor
        disc_total = disc_nbs_total + disc_res_total
        f.write(
            f"TOTAL (discounted), {sum_area:.2f}, {avg_res_pct:.2f}%, {avg_nbs_pct:.2f}%, {int(sum_trees)}, "
            f"{sum_res_area:.2f} m2, {sum_nbs_co2:.2f} kg, {disc_nbs_total:.2f} €, {sum_res_co2:.2f} kg, {disc_res_total:.2f} €, {sum_total_co2:.2f} kg, {disc_total:.2f} €\n"
        )


def write_single_solution_outputs(
    *,
    args,
    blocks,
    block_options: List[List[Options]],
    params: Params,
    point: Tuple[float, float],
    selection: Sequence[int],
    mode: str,
    extra_meta: Optional[dict] = None,
) -> None:
    # points CSV
    write_csv(args.out, [point], n_blocks=len(blocks))
    # metadata JSON
    if args.portfolios_out:
        os.makedirs(os.path.dirname(args.portfolios_out), exist_ok=True)
        meta = {
            'mode': mode,
            'n_blocks': len(blocks),
            'params': params.__dict__,
            'block_options': [[o.__dict__ for o in opts] for opts in block_options],
            'selection': list(selection),
            'blocks': blocks,
        }
        if extra_meta:
            meta.update(extra_meta)
        with open(args.portfolios_out, 'w') as f:
            json.dump(meta, f, indent=2)
    # per-block selection CSV (indices)
    if args.selections_out:
        write_selections_csv(args.selections_out, 0, point, blocks, block_options, selection)
    # detailed table CSV
    if args.table_out:
        write_table_csv(args.table_out, blocks, block_options, selection, params)


def main() -> None:
    ap = argparse.ArgumentParser(description='Compute Pareto front or single solution for uncovered spaces.')
    ap.add_argument('--uncovered-dir', required=True, help='Folder with Block_*.shp files, or a single unified .shp file')
    ap.add_argument('--options', required=True, help='Path to options.csv')
    ap.add_argument('--out', required=True, help='Output CSV path for frontier points')
    # Mode: frontier (steps) or single solve under budget
    ap.add_argument('--mode', choices=['frontier-steps', 'max-co2-under-budget', 'min-cost-above-co2', 'both-constraints'], default='frontier-steps', help='Solve mode')
    # OR-Tools budget frontier parameters (steps only)
    ap.add_argument('--budget-steps', type=int, default=0, help='Number of budget samples (>=2); 0 = auto-compute from problem size')
    ap.add_argument('--max-pct-res', type=float, default=100.0, help='Max % RES option allowed (0..100)')
    ap.add_argument('--max-pct-nbs', type=float, default=100.0, help='Max % NBS option allowed (0..100)')

    # Params mirrors NetLogo sliders
    ap.add_argument('--cost-res', type=float, default=240.0)
    ap.add_argument('--co2-res', type=float, default=71.0)
    ap.add_argument('--cost-nbs', type=float, default=600.0)
    ap.add_argument('--co2-nbs', type=float, default=25.0)
    ap.add_argument('--pct-covered-by-NBS-RES', type=float, default=50.0)
    ap.add_argument('--pct-covered-roof', type=float, default=-1.0, help='Coverage fraction for roof blocks (0..100); overrides --pct-covered-by-NBS-RES for roof blocks when >= 0')
    ap.add_argument('--pct-covered-ground', type=float, default=-1.0, help='Coverage fraction for ground blocks (0..100); overrides --pct-covered-by-NBS-RES for ground blocks when >= 0')
    ap.add_argument('--tree-cover-area', type=float, default=5.0)
    ap.add_argument('--tree-weight', type=float, default=400.0)
    ap.add_argument('--max-roof-load', type=float, default=100.0)
    ap.add_argument('--res-cell-area', type=float, default=5.0)
    # Economies of scale
    ap.add_argument('--res-cost-floor', type=float, default=1.0)
    ap.add_argument('--nbs-cost-floor', type=float, default=1.0)
    ap.add_argument('--res-discount-units', type=float, default=1e30)
    ap.add_argument('--nbs-discount-units', type=float, default=1e30)

    ap.add_argument('--budget-max', type=float, default=None, help='Budget limit in euros (required for max-co2-under-budget or both-constraints)')
    ap.add_argument('--co2-min', type=float, default=None, help='CO2 limit in kg (required for min-cost-above-co2 or both-constraints)')
    ap.add_argument('--portfolios-out', default=None, help='Optional JSON with per-run metadata')
    ap.add_argument('--selections-out', default=None, help='Optional CSV with per-block selection indices for the chosen solution')
    ap.add_argument('--table-out', default=None, help='Optional CSV table with per-block metrics and a TOTAL row')
    # Plot options are ignored (kept for compatibility)
    ap.add_argument('--plot-out', default=None, help=argparse.SUPPRESS)
    ap.add_argument('--plot-title', default='Cost vs CO2 Frontier', help=argparse.SUPPRESS)

    args = ap.parse_args()

    params = Params(
        cost_res=args.cost_res,
        co2_res=args.co2_res,
        cost_nbs=args.cost_nbs,
        co2_nbs=args.co2_nbs,
        pct_covered_by_NBS_RES=args.pct_covered_by_NBS_RES,
        pct_covered_roof=args.pct_covered_roof,
        pct_covered_ground=args.pct_covered_ground,
        tree_cover_area=args.tree_cover_area,
        tree_weight=args.tree_weight,
        max_roof_load=args.max_roof_load,
        res_cell_area=args.res_cell_area,
        res_cost_floor=args.res_cost_floor,
        nbs_cost_floor=args.nbs_cost_floor,
        res_discount_units=args.res_discount_units,
        nbs_discount_units=args.nbs_discount_units,
    )
    print("Params:", params)
    blocks = load_uncovered_blocks(args.uncovered_dir)
    print("Blocks:", blocks)

    options = load_ground_options(
        args.options,
        max_pct_res=args.max_pct_res / 100.0,
        max_pct_nbs=args.max_pct_nbs / 100.0,
    )
    print("Options:", options)

    block_opts, block_opt_refs = build_block_options(blocks, options, params)
    print("Block options (cost,co2):", block_opts)
    print("Block option refs:", block_opt_refs)

    # OR-Tools scaling and integer points
    scale = Scale(cost=1000, co2=1000)
    int_block_opts = [scale_points(opts, scale) for opts in block_opts]

    if args.mode == 'max-co2-under-budget':
        if args.budget_max is None:
            raise SystemExit('--budget-max is required for mode=max-co2-under-budget')
        budget_int = int(round(args.budget_max * scale.cost))
        print("Budget int", budget_int)
        sol = solve_max_co2_under_budget(int_block_opts, budget_int)
        print ("Solution", sol)
        if sol is None:
            # No feasible solution
            write_csv(args.out, [], n_blocks=len(blocks))
            # Overwrite selections/table outputs to avoid stale data
            if args.selections_out:
                os.makedirs(os.path.dirname(args.selections_out), exist_ok=True)
                with open(args.selections_out, 'w') as f:
                    f.write('solution_id,total_cost,total_co2,block_index,block_key,area_m2,res_pct,nbs_pct\n')
            if args.table_out:
                os.makedirs(os.path.dirname(args.table_out), exist_ok=True)
                with open(args.table_out, 'w') as f:
                    f.write('ID, Area_m2, RES%, NBS%, # Trees, RES_m2, NBS_CO2_kg, NBS_Cost_€, RES_CO2_kg, RES_Cost_€, Total_CO2_kg, Total_Cost_€\n')
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            block_options=block_opt_refs,
            params=params,
            point=point,
            selection=sel,
            mode='max-co2-under-budget',
            extra_meta={'budget_max': args.budget_max},
        )
        return

    if args.mode == 'min-cost-above-co2':
        if args.co2_min is None:
            raise SystemExit('--co2-min is required for mode=min-cost-above-co2')
        co2_int = int(round(args.co2_min * scale.co2))
        print("CO2 int", co2_int)
        sol = solve_min_cost_above_co2(int_block_opts, co2_int)
        print ("Solution", sol)
        if sol is None:
            write_csv(args.out, [], n_blocks=len(blocks))
            if args.selections_out:
                os.makedirs(os.path.dirname(args.selections_out), exist_ok=True)
                with open(args.selections_out, 'w') as f:
                    f.write('solution_id,total_cost,total_co2,block_index,block_key,area_m2,res_pct,nbs_pct\n')
            if args.table_out:
                os.makedirs(os.path.dirname(args.table_out), exist_ok=True)
                with open(args.table_out, 'w') as f:
                    f.write('ID, Area_m2, RES%, NBS%, # Trees, RES_m2, NBS_CO2_kg, NBS_Cost_€, RES_CO2_kg, RES_Cost_€, Total_CO2_kg, Total_Cost_€\n')
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            block_options=block_opt_refs,
            params=params,
            point=point,
            selection=sel,
            mode='min-cost-above-co2',
            extra_meta={'co2_min': args.co2_min},
        )
        return

    if args.mode == 'both-constraints':
        if args.budget_max is None or args.co2_min is None:
            raise SystemExit('--budget-max and --co2-min are required for mode=both-constraints')
        budget_int = int(round(args.budget_max * scale.cost))
        co2_int = int(round(args.co2_min * scale.co2))
        sol = solve_both_constraints(int_block_opts, budget_int, co2_int)
        if sol is None:
            write_csv(args.out, [], n_blocks=len(blocks))
            if args.selections_out:
                os.makedirs(os.path.dirname(args.selections_out), exist_ok=True)
                with open(args.selections_out, 'w') as f:
                    f.write('solution_id,total_cost,total_co2,block_index,block_key,area_m2,res_pct,nbs_pct\n')
            if args.table_out:
                os.makedirs(os.path.dirname(args.table_out), exist_ok=True)
                with open(args.table_out, 'w') as f:
                    f.write('ID, Area_m2, RES%, NBS%, # Trees, RES_m2, NBS_CO2_kg, NBS_Cost_€, RES_CO2_kg, RES_Cost_€, Total_CO2_kg, Total_Cost_€\n')
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            block_options=block_opt_refs,
            params=params,
            point=point,
            selection=sel,
            mode='both-constraints',
            extra_meta={'budget_max': args.budget_max, 'co2_min': args.co2_min},
        )
        return

    # Default: frontier by uniform budget steps
    min_budget = sum(min(c for (c, _) in opts) for opts in int_block_opts)
    max_budget = sum(max(c for (c, _) in opts) for opts in int_block_opts)
    # Auto budget steps: 3× total options across all blocks, clamped to [20, 300]
    if args.budget_steps <= 0:
        n_options_total = sum(len(opts) for opts in int_block_opts)
        budget_steps = max(20, min(300, n_options_total * 3))
        print(f"Auto budget-steps: {budget_steps} (from {n_options_total} total options)")
    else:
        budget_steps = args.budget_steps
    res = frontier_by_budget_steps(
        int_block_opts,
        min_budget,
        max_budget,
        steps=max(budget_steps, 2),
    )
    # Convert back to floats and compute unit counts per selection
    points = [(c / scale.cost, z / scale.co2) for (c, z, _sel) in res]
    selections = [sel for (_c, _z, sel) in res]
    counts = [compute_counts_for_selection(blocks, block_opt_refs, sel, params) for sel in selections]
    meta = {
        'mode': 'frontier-steps',
        'budget_steps': args.budget_steps,
        'n_blocks': len(blocks),
        'params': params.__dict__,
        'block_options': [[o.__dict__ for o in opts] for opts in block_opt_refs],
        'selections': selections,
        'min_budget': min_budget / scale.cost,
        'max_budget': max_budget / scale.cost,
        'blocks': blocks,
    }

    write_points_with_counts(args.out, points, counts, n_blocks=len(blocks), params=params)
    if args.portfolios_out:
        os.makedirs(os.path.dirname(args.portfolios_out), exist_ok=True)
        with open(args.portfolios_out, 'w') as f:
            json.dump(meta, f, indent=2)

    # plotting disabled by request


if __name__ == '__main__':
    main()
