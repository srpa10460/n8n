# CHECKPOINT-002  (supersedes CHECKPOINT-001; read AGENTS.md first)

## Where
- Repo: srpa10460/n8n (upstream n8n fork). Branch: `claude/cool-meitner-1tymfk` (pushed). Project dir: `homura-field-dx/`.
- Commits: 3287cb36 (core, CHECKPOINT-001) > a9c7d7a5 (offline-first PWA, sync, interference redesign) > the handoff commit that adds this file (`git log --oneline -5` on the branch). Base: upstream master 96d3faf3. No PR was created (not requested).
- Files outside `homura-field-dx/` changed vs base: 0.

## Done and VERIFIED (automated, this environment only)
- Core: units, versioned Catalog, instances, validation, approval gate, exports, derived Scene. 45 unit tests pass (`evidence/test_run_verbose.txt`).
- Interference redesigned into overlap / distance / required-space; 21 expected-vs-actual rows all match (`evidence/interference_cases.md`).
- Browser app (offline-first PWA): project, catalog, objects/placement, dims+units+datum, photos+annotations, validation, plan preview, review/approval (version+hash bound, confirmations, DEV_SIMULATED vs HUMAN_FINAL), export - all runnable offline. Domain logic is the Python core running in the browser via Pyodide 0.27.7 (same code the server uses).
- Sync: manual send, 5 visible states, idempotent begin/asset/commit, conflict diff + adopt/override, backup export/import. Browser E2E `tests/e2e_offline.py`: 41/41 checks (offline boot, quit/restart restore incl. photos, send, interrupted upload + retry w/o duplicates, edit-while-sending, auth expiry, version conflict, quota fault injection, backup import into a fresh profile). Screens: `docs/screens/*.png`.
- Defects found by running/rendering and fixed: overlapping plan labels; unclosed function in UI (page did not render); global server lock stalled static serving; same photo silently re-tagged on one object; stale-message race in the UI; stale sync state after conflict action.

## NOT verified / NOT implemented
- Any TARGET device (undecided). Everything is Chromium 141 headless on Linux. Persistence/quota/eviction on tablets/iOS Safari/Android Chrome is untested (OFF-8).
- Quota exhaustion was fault-injected (IDB put throws QuotaExceededError), not a real full disk.
- Real multi-device conflict (second device was simulated by another client id calling the API).
- HTTPS/VPS deployment and real authentication (dev-only HMAC token). Service Worker needs localhost/HTTPS.
- Photo->auto-draft, dimension constraints, door-swing/non-box interference, fractional-inch input.
- Does root-level n8n `pnpm lint/format` (biome) touch this dir? Not run.
- B (Blender), PDF manual, PR video, payment/pricing research: see "Next". Independent Guardian review: not performed.

## BLOCKED (needs Human / outside session)
- KC-HAO-HOA-001, SC-HAO-HOAP-001, GC-HAO-OUTCOME-001 originals: not found anywhere reachable (searched the repo and filesystem for the IDs). Spec uses only the instruction text.
- Target device model/OS/browser; VPS configuration/access; real authentication scheme; destination repo for migration.
- Real required-space values and real object catalog from the client (INT-4). Synthetic values are labelled as such.
- Everything under the stop conditions in AGENTS.md (billing Mina-san, real contract, external publication, paid purchases, production deploy, SSOT promotion).

## Local-only / environment dependencies (NOT in git)
- `static/vendor/pyodide/` (git-ignored): run `./scripts/fetch_pyodide.sh` (npm `pyodide@0.27.7`).
- Python venv with playwright 1.63.0, pymupdf 1.28.2, pypdf 6.19.0, reportlab 5.0.1, bpy 5.0.1: this session's was `/tmp/claude-0/bl/v` (ephemeral container). Recreate: `./scripts/setup_dev_env.sh` (versions in `requirements-dev.txt`).
- System Chromium 141 at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (sandbox-provided; override with `HOA_CHROME`). Do not run `playwright install`.
- Needs network once for pip/npm. node 22 / ffmpeg / pdftoppm exist in the sandbox (used or planned for media QA).
- Runtime data (`data/`, test temp profiles) is not kept; Evidence copies are committed under `evidence/`.

## Next (resume here, in order)
1. B-1/B-2: run `src/hoa_field/blender_build.py` with bpy (see below) from `evidence/e2e_offline/.../` approved export or `evidence/case1/approved/` (manifest.json + snapshot.json); verify dims/placement/hash; render still + 72-frame orbit with ffmpeg; LOOK at frames.
2. DOC-1: PDF manual from `docs/screens/*.png` (TOC internal links, bookmarks), then render with pdftoppm and inspect links (pypdf) and legibility.
3. VID-1: storyboard that only claims verified features (list in acceptance_spec.md); no numeric efficiency claims.
4. PAY-1: compare payment providers from official docs (no account creation), draft pricing from running cost/scope/support; test-mode only.
5. Move toward target device decision (OFF-8) and HTTPS dev deployment plan (needs 伊佐: device list, VPS).
6. Independent Guardian review if a separate reviewer becomes available; evidence is in `evidence/`, `docs/TRACEABILITY.md`.

🔳 Human decisions pending: target device list; VPS/HTTPS plan; destination repo for migration; real catalog/required-space inputs; whether to supply the three normative documents.
