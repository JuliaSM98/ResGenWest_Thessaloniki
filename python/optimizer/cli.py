import argparse
import json
import os
from typing import List, Sequence, Tuple, Optional

from .data import load_uncovered_blocks
from .options import load_ground_options
from .model import Params, compute_block_option_metrics
from .ortools_solver import (
    Scale,
    scale_points,
    frontier_by_budget_steps,
    solve_max_co2_under_budget,
    solve_min_cost_above_co2,
    solve_both_constraints,
)


def build_block_options(blocks, options, params: Params) -> List[List[Tuple[float, float]]]:
    block_opts: List[List[Tuple[float, float]]] = []
    for b in blocks:
        area = float(b['area_m2'])
        opts = []
        for o in options:
            c, z = compute_block_option_metrics(area, o.res_pct, o.nbs_pct, params)
            opts.append((c, z))
        block_opts.append(opts)
    return block_opts


def write_csv(out_path: str, points: Sequence[Tuple[float, float]], n_blocks: int) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('cost,co2,n_blocks\n')
        for c, z in points:
            f.write(f"{c:.6f},{z:.6f},{n_blocks}\n")


def write_selections_csv(path: str, solution_id: int, point: Tuple[float, float], blocks, options, selection: Sequence[int]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('solution_id,total_cost,total_co2,block_index,block_key,area_m2,mix_id,res_pct,nbs_pct\n')
        for i, choice_idx in enumerate(selection):
            b = blocks[i]
            o = options[choice_idx]
            f.write(
                f"{solution_id},{point[0]:.6f},{point[1]:.6f},{i},{b.get('block')},{float(b['area_m2']):.6f},{o.mix_id},{o.res_pct:.6f},{o.nbs_pct:.6f}\n"
            )


def write_table_csv(path: str, blocks, options, selection: Sequence[int], params: Params) -> None:
    """Write a detailed table matching NetLogo's render-current-table output."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cov = max(0.0, min(100.0, params.pct_covered_by_NBS_RES)) / 100.0
    with open(path, 'w') as f:
        f.write('ID, Area_m2, RES%, NBS%, # Trees, RES_m2, NBS_CO2_kg, NBS_Cost_€, RES_CO2_kg, RES_Cost_€, Total_CO2_kg, Total_Cost_€\n')
        sum_area = sum_trees = 0.0
        sum_res_area = sum_nbs_co2 = sum_nbs_cost = 0.0
        sum_res_co2 = sum_res_cost = 0.0
        sum_total_co2 = sum_total_cost = 0.0
        res_pct_sum = nbs_pct_sum = 0.0
        n = len(blocks)
        for i, choice_idx in enumerate(selection):
            b = blocks[i]
            area = float(b['area_m2'])
            o = options[choice_idx]
            res_pct = max(0.0, o.res_pct)
            nbs_pct = max(0.0, o.nbs_pct)
            res_area = area * cov * res_pct
            eff_nbs_area = area * cov * nbs_pct
            trees = int(eff_nbs_area // max(1e-9, params.tree_cover_area))
            nbs_co2 = trees * params.co2_nbs
            nbs_cost = trees * params.cost_nbs
            res_co2 = res_area * params.co2_res
            res_cost = res_area * params.cost_res
            total_co2 = nbs_co2 + res_co2
            total_cost = nbs_cost + res_cost
            sum_area += area
            sum_trees += trees
            sum_res_area += res_area
            sum_nbs_co2 += nbs_co2
            sum_nbs_cost += nbs_cost
            sum_res_co2 += res_co2
            sum_res_cost += res_cost
            sum_total_co2 += total_co2
            sum_total_cost += total_cost
            res_pct_sum += (res_pct * 100.0)
            nbs_pct_sum += (nbs_pct * 100.0)
            f.write(
                f"{b.get('block')}, {area:.6f}, {res_pct*100.0:.2f}%, {nbs_pct*100.0:.2f}%, {trees}, "
                f"{res_area:.2f} m2, {nbs_co2:.2f} kg, {nbs_cost:.2f} €, {res_co2:.2f} kg, {res_cost:.2f} €, {total_co2:.2f} kg, {total_cost:.2f} €\n"
            )
        avg_res_pct = (res_pct_sum / n) if n > 0 else 0.0
        avg_nbs_pct = (nbs_pct_sum / n) if n > 0 else 0.0
        f.write(
            f"TOTAL, {sum_area:.2f}, {avg_res_pct:.2f}%, {avg_nbs_pct:.2f}%, {int(sum_trees)}, "
            f"{sum_res_area:.2f} m2, {sum_nbs_co2:.2f} kg, {sum_nbs_cost:.2f} €, {sum_res_co2:.2f} kg, {sum_res_cost:.2f} €, {sum_total_co2:.2f} kg, {sum_total_cost:.2f} €\n"
        )


def write_single_solution_outputs(
    *,
    args,
    blocks,
    options,
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
            'options': [o.__dict__ for o in options],
            'selection': list(selection),
            'blocks': blocks,
        }
        if extra_meta:
            meta.update(extra_meta)
        with open(args.portfolios_out, 'w') as f:
            json.dump(meta, f, indent=2)
    # per-block selection CSV (indices)
    if args.selections_out:
        write_selections_csv(args.selections_out, 0, point, blocks, options, selection)
    # detailed table CSV
    if args.table_out:
        write_table_csv(args.table_out, blocks, options, selection, params)


def main() -> None:
    ap = argparse.ArgumentParser(description='Compute Pareto front or single solution for uncovered spaces.')
    ap.add_argument('--uncovered-dir', required=True, help='Folder with Block_*.shp files, or a single unified .shp file')
    ap.add_argument('--options', required=True, help='Path to options.csv')
    ap.add_argument('--out', required=True, help='Output CSV path for frontier points')
    # Mode: frontier (steps) or single solve under budget
    ap.add_argument('--mode', choices=['frontier-steps', 'max-co2-under-budget', 'min-cost-above-co2', 'both-constraints'], default='frontier-steps', help='Solve mode')
    # OR-Tools budget frontier parameters (steps only)
    ap.add_argument('--budget-steps', type=int, default=41, help='Number of budget samples (>=2)')
    ap.add_argument('--max-pct-res', type=float, default=100.0, help='Max % RES option allowed (0..100)')
    ap.add_argument('--max-pct-nbs', type=float, default=100.0, help='Max % NBS option allowed (0..100)')

    # Params mirrors NetLogo sliders
    ap.add_argument('--cost-res', type=float, default=240.0)
    ap.add_argument('--co2-res', type=float, default=48.0)
    ap.add_argument('--cost-nbs', type=float, default=600.0)
    ap.add_argument('--co2-nbs', type=float, default=25.0)
    ap.add_argument('--pct-covered-by-NBS-RES', type=float, default=50.0)
    ap.add_argument('--tree-cover-area', type=float, default=5.0)

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
        tree_cover_area=args.tree_cover_area,
    )

    blocks = load_uncovered_blocks(args.uncovered_dir)

    options = load_ground_options(
        args.options,
        max_pct_res=args.max_pct_res / 100.0,
        max_pct_nbs=args.max_pct_nbs / 100.0,
    )

    block_opts = build_block_options(blocks, options, params)

    # OR-Tools scaling and integer points
    scale = Scale(cost=100, co2=100)
    int_block_opts = [scale_points(opts, scale) for opts in block_opts]

    if args.mode == 'max-co2-under-budget':
        if args.budget_max is None:
            raise SystemExit('--budget-max is required for mode=max-co2-under-budget')
        budget_int = int(round(args.budget_max * scale.cost))
        sol = solve_max_co2_under_budget(int_block_opts, budget_int)
        if sol is None:
            # No feasible solution
            write_csv(args.out, [], n_blocks=len(blocks))
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            options=options,
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
        sol = solve_min_cost_above_co2(int_block_opts, co2_int)
        if sol is None:
            write_csv(args.out, [], n_blocks=len(blocks))
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            options=options,
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
            return
        c_int, z_int, sel = sol
        point = (c_int / scale.cost, z_int / scale.co2)
        write_single_solution_outputs(
            args=args,
            blocks=blocks,
            options=options,
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
    res = frontier_by_budget_steps(
        int_block_opts,
        min_budget,
        max_budget,
        steps=max(args.budget_steps, 2),
    )
    # Convert back to floats
    points = [(c / scale.cost, z / scale.co2) for (c, z, _sel) in res]
    selections = [sel for (_c, _z, sel) in res]
    meta = {
        'mode': 'frontier-steps',
        'budget_steps': args.budget_steps,
        'n_blocks': len(blocks),
        'params': params.__dict__,
        'options': [o.__dict__ for o in options],
        'selections': selections,
        'min_budget': min_budget / scale.cost,
        'max_budget': max_budget / scale.cost,
        'blocks': blocks,
    }

    write_csv(args.out, points, n_blocks=len(blocks))
    if args.portfolios_out:
        os.makedirs(os.path.dirname(args.portfolios_out), exist_ok=True)
        with open(args.portfolios_out, 'w') as f:
            json.dump(meta, f, indent=2)

    # plotting disabled by request


if __name__ == '__main__':
    main()
