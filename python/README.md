Python Optimizer for Pareto Front (Uncovered Spaces)

Overview
- Goal: compute Pareto-efficient portfolios over uncovered space blocks by choosing one of the ground options per block to trade off total Cost (€) vs CO2 (kg).
- Data: reads uncovered blocks either from a directory of `Block_*.shp` (summing `Area_Uncov` per block) or from a single unified shapefile (e.g., `data/shapefiles/uncovered_spaces/uncovered_spaces_all.shp`) with columns `Id`, `B_Number`, and `Area_U_m2` (summing per `Id.B_Number`). Uses `data/csv/options.csv` (filters `cell_type=ground`).
- Assumptions: one option per block; cost/CO2 intensities and tree layout parameters mirror the NetLogo sliders.

Install
1) Create a virtual environment and install deps:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`

Run
- OR-Tools budget frontier (maximize CO2 for each budget):
  - Tight frontier (auto budgets):
    - Dir input: `python -m optimizer.cli --uncovered-dir ../data/shapefiles/uncovered_spaces --options ../data/csv/options.csv --budget-mode tight --out ../data/outputs/pareto_uncovered_ortools.csv --plot-out ../data/outputs/pareto_uncovered_ortools.png`
    - Unified file: `python -m optimizer.cli --uncovered-dir ../data/shapefiles/uncovered_spaces/uncovered_spaces_all.shp --options ../data/csv/options.csv --budget-mode tight --out ../data/outputs/pareto_uncovered_ortools.csv --plot-out ../data/outputs/pareto_uncovered_ortools.png`
  - Uniform budget steps between min and max cost:
    - `python -m optimizer.cli --uncovered-dir ../data/shapefiles/uncovered_spaces --options ../data/csv/options.csv --budget-mode steps --budget-steps 41 --out ../data/outputs/pareto_uncovered_ortools_steps.csv  --plot-out ../data/outputs/pareto_uncovered_ortools.png`
  - Save a plot of the frontier:
    - add `--plot-out ../data/outputs/pareto_uncovered_ortools.png` (optional `--plot-title "My Title"`)
  - Performance knobs (both default OFF):
    - Add `--refine-lexicographic` to minimize cost among max-CO2 solutions (slower; ensures cost-minimal tie-breaks).
    - Add `--prune-frontier` to drop dominated points post-hoc (cheap; removes weakly dominated duplicates).
  

Parameters (optional)
- `--cost-res`, `--co2-res`: €/m2 and kg/(m2·year) for RES.
- `--cost-nbs`, `--co2-nbs`: €/tree and kg/(tree·year) for NBS.
- `--pct-covered-by-trees`: % of the NBS area actually covered by trees (0–100).
- `--tree-cover-area`: m2 occupied per tree.
- `--max-pct-res`, `--max-pct-nbs`: upper bounds (0–100) on option res/nbs percentages to consider.

Outputs
- CSV with Pareto points: columns `cost`, `co2`, `n_blocks`.
- Metadata JSON via `--portfolios-out` containing: params, options, blocks (block ids and areas), selections (option index per block for each frontier point), and budget range.
 - PNG plot (if `--plot-out` is passed): Cost (€) on X, CO2 (kg) on Y, sorted by cost.

Notes
- All geometries inside a block share one decision; we aggregate block area first.
- OR-Tools mode uses CP-SAT with integer-scaled costs/CO2 (cents and 0.01 kg) to maximize `CO2` under a budget. The `tight` mode walks budget breakpoints by repeatedly constraining cost to below the last optimum.
