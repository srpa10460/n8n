#!/usr/bin/env bash
# Recreates the dev environment used for the recorded Evidence. Needs network once. Creates ./.venv (git-ignored).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
./scripts/fetch_pyodide.sh
echo "OK. Run all checks:  ./scripts/run_all_tests.sh"
