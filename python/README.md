Python Optimizer for Pareto Front (Unified Shapefile)

Overview
- Goal: compute Pareto-efficient portfolios over blocks by choosing one option per block to trade off total Cost (€) vs CO2 (kg).
- Data: reads a single unified shapefile (e.g., `data/shapefiles/uncovered_spaces/uncovered_spaces_all.shp`) with columns `Id`, `B_Number`, and one or both of `Area_U_m2` (ground) and `Area_R_m2` (roof). Aggregates areas per `Id.B_Number` and cell type. Uses `data/csv/options.csv` (filtered by `cell_type`).
- Assumptions: one option per block; cost/CO2 intensities and tree layout parameters mirror the NetLogo sliders.

Install
1) Create a virtual environment and install deps:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`

Run
- OR-Tools budget frontier (maximize CO2 for each budget):
  - Uniform budget steps between min and max cost (steps only):
    - `python -m optimizer.cli --uncovered-dir ../data/shapefiles/uncovered_spaces/uncovered_spaces_all.shp --options ../data/csv/options.csv --budget-steps 41 --out ../data/outputs/pareto_uncovered_ortools.csv`
  - The simplified optimizer uses a single-phase solve per budget without extra tie-breaking or pruning.
  

Parameters (optional)
- `--cost-res`, `--co2-res`: €/m2 and kg/(m2·year) for RES.
- `--cost-nbs`, `--co2-nbs`: €/tree and kg/(tree·year) for NBS.
- `--pct-covered-by-NBS-RES`: % of the NBS area actually covered by trees (0–100).
- `--tree-cover-area`: m2 occupied per tree.
- `--max-pct-res`, `--max-pct-nbs`: upper bounds (0–100) on option res/nbs percentages to consider.

Outputs
- CSV with Pareto points: columns `cost`, `co2`, `n_blocks`.
- Metadata JSON via `--portfolios-out` containing: params, options, blocks (block ids and areas), selections (option index per block for each frontier point), and budget range.

Notes
- All geometries inside a block share one decision; we aggregate block area first per cell type (`roof`/`ground`).
- OR-Tools mode uses CP-SAT with integer-scaled costs/CO2 (cents and 0.01 kg) to maximize `CO2` under a budget.
