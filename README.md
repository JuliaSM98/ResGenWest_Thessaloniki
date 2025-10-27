ReGenWest Schools Portfolio (NetLogo)

Overview
- Goal: explore portfolios of interventions on school blocks by combining renewable energy (PV/RES) and nature‑based solutions (NBS/trees) to understand cost vs. CO2 trade‑offs.
- Approach: load a GIS shapefile of blocks, combine with CSV catalogs of feasible mixes and intensity assumptions, then enumerate/sample portfolios and plot total cost and CO2.
- Context: built for the Thessaloniki study area included in this repository.

How It Works
- GIS: load the blocks shapefile and aggregate per‑block areas for each cell type (roof/ground).
- Catalogs: read `options.csv` (available mixes per cell type) and `cost_co2_assumptions.csv` (cost/CO2 intensities per action).
- Sampling: for each block+cell‑type, choose one feasible option (mix). Compute portfolio totals by multiplying areas by intensity values for RES and NBS actions.
- Plotting: add points to cost, CO2, and “Cost vs CO2” plots to reveal trade‑offs across portfolios.

Repo Structure
- `schools_project.nlogo` — main NetLogo model (Interface + includes).
- `src/utils.nls` — utilities (number parsing, column lookup, percent normalization, joins, products).
- `src/csv_io.nls` — CSV loaders and preview helpers.
- `src/gis.nls` — shapefile loading, ID/area aggregation, drawing, listing.
- `src/catalogs.nls` — build option catalogs and cost/CO2 intensity tables.
- `src/sampler.nls` — portfolio sampler/enumerator, keying, totals computation, annotation.
- `src/core.nls` — orchestration for `setup` and `go`.
- `data/csv/` — input CSVs (`options.csv`, `cost_co2_assumptions.csv`).
- `data/shapefiles/` — GIS data for the study area.

Setup
- Install NetLogo (6.3+ recommended). Ensure extensions `gis`, `table`, and `csv` are available.
- Verify input files exist:
  - `data/csv/options.csv`
  - `data/csv/cost_co2_assumptions.csv`
  - `data/shapefiles/Schools_B_R_U.shp` (plus `.shx`, `.dbf`, `.prj`, etc.)

Run (GUI)
- Open `schools_project.nlogo` in NetLogo.
- In the Interface tab, click `setup` then `go` to enumerate/sample and plot portfolios.

Data Schemas
- `options.csv` (one row per feasible mix):
  - `mix_id` — unique option ID per cell type.
  - `cell_type` — `roof` or `ground`.
  - `res_pct` — share of area for RES/PV (0–1 or 0–100%).
  - `nbs_pct` — share of area for NBS/trees (0–1 or 0–100%).
  - `label` — human‑readable description.
- `cost_co2_assumptions.csv` (intensities):
  - `action_id` — e.g., `RES`, `NBS`.
  - `cost_per_m2` — cost intensity.
  - `co2_per_m2` — yearly CO2 intensity.
- `Schools_B_R_U.shp` attributes used:
  - `Id` — project ID, numeric/string.
  - `B_Number` — block number within the project.
  - `Area_R_m2` — area in m² contributing to roof cell type.
  - `Area_U_m2` — area in m² contributing to ground cell type.
  - `Area_B_m2` — total block area (not used for calculations).
  - Block ID defined as `Id.B_Number`. Multiple geometries per block are aggregated by summing areas. Internally, entries are tracked per cell type as `Id.B_Number:roof` and `Id.B_Number:ground` when the area is greater than zero.

Notes and Assumptions
- The GIS reader aggregates areas across multiple geometries; empty or missing area attributes are treated as zero.
- Options are selected per cell type (`roof`/`ground`) and applied to the corresponding aggregated area.
- The plots show raw totals; extend with normalization, constraints, or filtering as needed.

Extending
- Add new actions or cell types by updating the CSVs and, if needed, the lookup logic in `src/sampler.nls`.
- Consider filling in the documentation blocks inside `schools_project.nlogo` (WHAT IS IT, HOW IT WORKS, etc.) to align with course deliverables.
