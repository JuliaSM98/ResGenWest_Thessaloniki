Project: Schools Portfolio (NetLogo)

Overview
- Main model: `schools_project.nlogo`
- Code is modularized under `src/*.nls` for clarity.
- Extensions used: `gis`, `table`, `csv` (ensure installed in NetLogo).

Modules
- `src/utils.nls` — shared helpers (string/number conversions, joins, products, column lookup, percent normalization).
- `src/csv_io.nls` — CSV loading and preview.
- `src/gis.nls` — shapefile loading, ID table building, drawing, listing.
- `src/catalogs.nls` — build option catalogs and intensity lookups from CSVs.
- `src/sampler.nls` — sampler init, portfolio sampling, totals computation.
- `src/core.nls` — top-level `setup` and `go` procedures.
- `src/experiments.nls` — placeholder for experiment-specific helpers.

How to Run (GUI)
- Open `schools_project.nlogo` in NetLogo.
- In the Interface tab, click `setup` then `go`.

Headless Runs
- Use the provided `run.sh` wrapper (requires NetLogo’s `netlogo-headless.sh`).
- Defaults:
  - `MODEL=schools_project.nlogo`
  - `EXP=smoke` (change to your BehaviorSpace experiment name)

Examples
- `./run.sh` — runs default model/experiment, writes table output to `last_run.csv`.
- `MODEL=schools_project.nlogo EXP=my-experiment ./run.sh`
- `NETLOGO=/path/to/netlogo-headless.sh ./run.sh`

BehaviorSpace
- Define experiments in the `.nlogo` (BehaviorSpace dialog). Name them and reference via `EXP`.

Data Files
- CSVs (versioned in repo):
  - `data/csv/options.csv`
  - `data/csv/cost_co2_assumptions.csv`
- Shapefile components (versioned in repo):
  - `data/shapefiles/6.shp` (plus `.shx`, `.dbf`, `.prj`, etc.)

Notes
- Globals and extensions are kept in `.nlogo` for clarity; procedures live in `src/*.nls`.
- If you add new helpers, prefer creating/using a focused `src/*.nls` file and include it in `schools_project.nlogo`.
- Intensities CSV columns:
  - `action_id, co2_per_m2, cost_per_m2`
