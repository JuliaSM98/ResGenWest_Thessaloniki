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

# Ensure Python can import the optimizer package
export PYTHONPATH="$REPO_ROOT/python${PYTHONPATH:+:$PYTHONPATH}"

# Read all CLI args from NetLogo-generated file to avoid hardcoded paths
EXTRA_ARGS_FILE="$REPO_ROOT/data/outputs/optimizer_args.txt"
if [[ ! -f "$EXTRA_ARGS_FILE" ]]; then
  echo "ERROR: Missing $EXTRA_ARGS_FILE. Run setup and the optimizer button in NetLogo first." >&2
  exit 1
fi

args=( -m optimizer.cli )
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^# ]] && continue
  args+=( "$line" )
done < "$EXTRA_ARGS_FILE"

# Ensure output directory exists if --out=... is provided
for tok in "${args[@]}"; do
  case "$tok" in
    --out=*) out_path="${tok#--out=}"; mkdir -p "$(dirname "$out_path")" ;;
  esac
done

exec "$PYTHON_BIN" "${args[@]}"
