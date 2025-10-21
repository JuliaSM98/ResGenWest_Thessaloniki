#!/usr/bin/env bash
set -euo pipefail

#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (this script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Python interpreter (override by setting PYTHON env)
# Bootstrap local virtualenv if missing, to be boss-friendly
VENV_DIR="$REPO_ROOT/python/.venv"
REQS_FILE="$REPO_ROOT/python/requirements.txt"

# Prefer existing venv
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Setting up local Python environment at $VENV_DIR ..."
  # Find a system python to create the venv
  SYS_PY=""
  if command -v python3 >/dev/null 2>&1; then
    SYS_PY="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    SYS_PY="$(command -v python)"
  else
    echo "ERROR: No system python found. Please install Python 3 and retry." >&2
    exit 127
  fi
  "$SYS_PY" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  if [[ -f "$REQS_FILE" ]]; then
    echo "Installing Python requirements ..."
    "$VENV_DIR/bin/python" -m pip install -r "$REQS_FILE"
  fi
fi

PYTHON_BIN="$VENV_DIR/bin/python"

# Inputs (customize as needed or override via env)
UNCO_DIR="${UNCO_DIR:-data/shapefiles/uncovered_spaces/uncovered_spaces_all.shp}"
OPTIONS_CSV="${OPTIONS_CSV:-data/csv/options.csv}"
OUT_CSV="${OUT_CSV:-data/outputs/pareto_uncovered_ortools.csv}"
OUT_PNG="${OUT_PNG:-data/outputs/pareto_uncovered_ortools.png}"

# Frontier settings (override via env)
BUDGET_MODE="${BUDGET_MODE:-steps}"
BUDGET_STEPS="${BUDGET_STEPS:-41}"
REFINE="${REFINE:-0}"    # 1 to enable --refine-lexicographic
PRUNE="${PRUNE:-0}"      # 1 to enable --prune-frontier

mkdir -p "$(dirname "$OUT_CSV")"

# Ensure Python can import the optimizer package
export PYTHONPATH="$REPO_ROOT/python${PYTHONPATH:+:$PYTHONPATH}"

args=( -m optimizer.cli \
  --uncovered-dir "$UNCO_DIR" \
  --options "$OPTIONS_CSV" \
  --budget-mode "$BUDGET_MODE" \
  --out "$OUT_CSV" \
  --plot-out "$OUT_PNG" )

if [[ "$BUDGET_MODE" == "steps" ]]; then
  args+=( --budget-steps "$BUDGET_STEPS" )
fi
if [[ "$REFINE" == "1" ]]; then
  args+=( --refine-lexicographic )
fi
if [[ "$PRUNE" == "1" ]]; then
  args+=( --prune-frontier )
fi

# Append extra args from file (one token per line, use --flag=value form)
EXTRA_ARGS_FILE="$REPO_ROOT/data/outputs/optimizer_args.txt"
if [[ -f "$EXTRA_ARGS_FILE" ]]; then
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue
    args+=( "$line" )
  done < "$EXTRA_ARGS_FILE"
fi

exec "$PYTHON_BIN" "${args[@]}"
