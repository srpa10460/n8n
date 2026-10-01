#!/usr/bin/env bash
# Vendors Pyodide 0.27.7 (npm package "pyodide", MPL-2.0) into static/vendor/pyodide. Needs network once.
# The binaries are NOT committed (see .gitignore); run this after a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."
VER=0.27.7
TMP=$(mktemp -d)
( cd "$TMP" && npm pack "pyodide@$VER" >/dev/null && tar xzf "pyodide-$VER.tgz" )
mkdir -p static/vendor/pyodide
for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do cp "$TMP/package/$f" static/vendor/pyodide/; done
echo "$VER" > static/vendor/pyodide/VERSION
sha256sum static/vendor/pyodide/* > static/vendor/pyodide.sha256
echo "pyodide $VER vendored"
