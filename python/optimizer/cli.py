import argparse
import json
import os
from typing import List, Sequence, Tuple

from .data import load_uncovered_blocks
from .options import load_ground_options
from .model import Params, compute_block_option_metrics
from .ortools_solver import Scale, scale_points, frontier_by_budget_tight, frontier_by_budget_steps


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


def main() -> None:
    ap = argparse.ArgumentParser(description='Compute Pareto front for uncovered spaces.')
    ap.add_argument('--uncovered-dir', required=True, help='Folder with Block_*.shp files, or a single unified .shp file')
    ap.add_argument('--options', required=True, help='Path to options.csv')
    ap.add_argument('--out', required=True, help='Output CSV path for frontier points')
    # OR-Tools budget frontier parameters
    ap.add_argument('--budget-mode', choices=['tight', 'steps'], default='tight', help='Budget sweep strategy for ortools')
    ap.add_argument('--budget-steps', type=int, default=41, help='Steps for steps budget mode')
    ap.add_argument('--refine-lexicographic', action='store_true', help='Minimize cost among max-CO2 plans (slower)')
    ap.add_argument('--prune-frontier', action='store_true', help='Prune dominated points in the final frontier')
    ap.add_argument('--max-pct-res', type=float, default=100.0, help='Max % RES option allowed (0..100)')
    ap.add_argument('--max-pct-nbs', type=float, default=100.0, help='Max % NBS option allowed (0..100)')

    # Params mirrors NetLogo sliders
    ap.add_argument('--cost-res', type=float, default=240.0)
    ap.add_argument('--co2-res', type=float, default=48.0)
    ap.add_argument('--cost-nbs', type=float, default=600.0)
    ap.add_argument('--co2-nbs', type=float, default=25.0)
    ap.add_argument('--pct-covered-by-trees', type=float, default=50.0)
    ap.add_argument('--tree-cover-area', type=float, default=5.0)

    ap.add_argument('--portfolios-out', default=None, help='Optional JSON with per-run metadata')
    ap.add_argument('--plot-out', default=None, help='Optional path to save Cost vs CO2 plot (PNG)')
    ap.add_argument('--plot-title', default='Cost vs CO2 Frontier', help='Optional plot title')

    args = ap.parse_args()

    params = Params(
        cost_res=args.cost_res,
        co2_res=args.co2_res,
        cost_nbs=args.cost_nbs,
        co2_nbs=args.co2_nbs,
        pct_covered_by_trees=args.pct_covered_by_trees,
        tree_cover_area=args.tree_cover_area,
    )

    blocks = load_uncovered_blocks(args.uncovered_dir)

    options = load_ground_options(
        args.options,
        max_pct_res=args.max_pct_res / 100.0,
        max_pct_nbs=args.max_pct_nbs / 100.0,
    )

    block_opts = build_block_options(blocks, options, params)

    # OR-Tools: maximize CO2 under budget across the budget range
    scale = Scale(cost=100, co2=100)
    # Build int points per block
    int_block_opts = [scale_points(opts, scale) for opts in block_opts]
    # Compute min/max budget range
    min_budget = sum(min(c for (c, _) in opts) for opts in int_block_opts)
    max_budget = sum(max(c for (c, _) in opts) for opts in int_block_opts)
    if args.budget_mode == 'tight':
        res = frontier_by_budget_tight(int_block_opts, max_budget, refine_lexicographic=args.refine_lexicographic, prune=args.prune_frontier)
    else:
        res = frontier_by_budget_steps(int_block_opts, min_budget, max_budget, steps=args.budget_steps, refine_lexicographic=args.refine_lexicographic, prune=args.prune_frontier)
    # Convert back to floats
    points = [(c / scale.cost, z / scale.co2) for (c, z, _sel) in res]
    selections = [sel for (_c, _z, sel) in res]
    meta = {
        'mode': 'ortools',
        'budget_mode': args.budget_mode,
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

    if args.plot_out:
        # Lazy import and use non-interactive backend
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        os.makedirs(os.path.dirname(args.plot_out), exist_ok=True)
        xs = [c for c, _ in points]
        ys = [z for _, z in points]
        # Sort by cost to draw a monotone line
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        xs = [xs[i] for i in order]
        ys = [ys[i] for i in order]
        plt.figure(figsize=(6, 4))
        plt.plot(xs, ys, marker='o', linestyle='-', color='#1f77b4')
        plt.xlabel('Cost (€)')
        plt.ylabel('CO2 (kg)')
        plt.title(args.plot_title)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(args.plot_out, dpi=150)


if __name__ == '__main__':
    main()
