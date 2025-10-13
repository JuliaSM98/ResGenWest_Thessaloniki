#!/usr/bin/env bash
set -euo pipefail

# Adjust this path if netlogo-headless.sh isn’t on PATH
NETLOGO="${NETLOGO:-netlogo-headless.sh}"
MODEL="${MODEL:-schools_project.nlogo}"
EXP="${EXP:-smoke}"

# Write table output to stdout for quick feedback
"$NETLOGO" --model "$MODEL" --experiment "$EXP" --table - | tee last_run.csv

