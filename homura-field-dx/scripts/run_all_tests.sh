#!/usr/bin/env bash
# Runs every automated check. Exit code != 0 on any failure.
# HOA_PY: python with playwright+pymupdf (default .venv/bin/python). HOA_CHROME: Chromium binary.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${HOA_PY:-.venv/bin/python}"
echo "== unit + interference cases (stdlib) =="; python3 -m unittest discover -s tests -v 2>&1 | tail -4
echo "== browser E2E: offline-first + sync =="; "$PY" tests/e2e_offline.py | tail -3
