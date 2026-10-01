#!/usr/bin/env bash
# Runs every automated check. Exit code != 0 on any failure.
# HOA_PY: python with playwright+pymupdf+pypdf+bpy (default .venv/bin/python). HOA_CHROME: Chromium binary.
# bpy needs OS libs (libegl1, libgl1, libxkbcommon0, libsm6, libxi6, libxxf86vm1, libxfixes3, libxrender1, libgomp1).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${HOA_PY:-.venv/bin/python}"
echo "== unit + interference + billing sim + blender guards (stdlib) =="; python3 -m unittest discover -s tests -v 2>&1 | tail -4
echo "== browser E2E: offline-first + sync (regenerates docs/screens) =="; "$PY" tests/e2e_offline.py | tail -2
echo "== B: Blender build from approved export (evidence/blender) =="
python3 cases/run_representative.py evidence/case1 >/dev/null
rm -rf evidence/blender; PYTHONPATH=src "$PY" -m hoa_field.blender_build evidence/case1/approved evidence/blender 72 | tail -1; rm -rf evidence/blender/frames
echo "== manual PDF build + render QA =="; "$PY" scripts/build_manual.py; "$PY" scripts/qa_manual.py | grep -c PASS
