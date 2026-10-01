# AGENTS.md - HOMURA Interior Field DX (project-local)

Applies ONLY to files under `homura-field-dx/`. The upstream n8n rules (repo-root CLAUDE.md, pnpm/turbo conventions, Linear/PR conventions) are NOT changed and do NOT govern this directory's Python/ES-module code. Do not edit anything outside this directory for this project.

## Read first (in this order)
1. `checkpoints/CHECKPOINT-002.md` (latest) - where to resume, BLOCKED list, local-only dependencies
2. `docs/SPEC.md` - common spec: roles of A/B, offline requirements, stop conditions
3. `docs/acceptance_spec.md` - acceptance status per ID
4. `docs/TRACEABILITY.md` - requirement -> code -> test -> evidence
5. `docs/n8n_impact_and_migration.md` - why this lives inside an n8n fork and the (unexecuted) move plan
The originals of KC-HAO-HOA-001, SC-HAO-HOAP-001, GC-HAO-OUTCOME-001 are NOT in this repo. Do not infer their content from the IDs. Do not add approval conditions or norms to any file here unless they come from a document you can actually read or from 伊佐's explicit instruction.

## Work scope
- A (field app): `src/hoa_field/{units,catalog,project,interference,engine,export,scene,diff}.py`, `static/*` (PWA), `src/hoa_field/server.py` (sync only).
- B interface: `src/hoa_field/scene.py`, `src/hoa_field/blender_build.py`, exports (`manifest.json`, `snapshot.json`).
- Media/commercial work (manual, PR video, pricing): see acceptance IDs DOC-1, VID-1, PAY-1.
- Architecture rule: ONE implementation of domain logic = Python `engine.py` + modules it calls. The browser runs it via Pyodide; the server re-verifies with the same code. Never re-implement validation/interference/hash logic in JavaScript or in server handlers.
- Persistence rule: a write is "saved" only after IndexedDB `tx.oncomplete` (`static/db.js writeAll`). Never display saved on failure. Never auto-delete unsent device data.

## How to verify (run before and after any change)
- One-time env: `./scripts/setup_dev_env.sh` (creates `.venv`, installs `requirements-dev.txt`, vendors Pyodide). Needs network once.
- Everything: `./scripts/run_all_tests.sh` (stdlib `unittest`; browser E2E `tests/e2e_offline.py` with Chromium; Blender build via bpy; manual PDF build + QA). bpy needs OS libs listed in the script header (apt: libegl1 etc.). Env overrides: `HOA_PY` (python with playwright+pymupdf), `HOA_CHROME` (Chromium binary; default is the sandbox's `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`).
- Unit only (no deps): `python3 -m unittest discover -s tests -v` (58 tests at CHECKPOINT-002).
- Run the app: `HOA_DEV_AUTH=1 PYTHONPATH=src python3 -m hoa_field.server 8765` then open http://127.0.0.1:8765/ (service workers need localhost or HTTPS). Data dir `./data` (git-ignored) or `$HOA_DATA`.
- Visual checks: render screens with the E2E (`docs/screens/*.png`) and LOOK at them; two real defects (overlapping labels, missing closing brace in the UI) were found only by rendering/running.
- Report test counts AND what the browser actually completed. Do not call a mock/plan "done". Keep implemented / verified / unverified / BLOCKED separate.

## Stop conditions (do NOT do without 伊佐's explicit approval; wording from the instructions)
- start billing to Mina-san; enable any real contract / production subscription
- external publication; general sales start; production deploy
- buy paid services; sign new contracts such as a VPS
- delete production data or make irreversible changes to it
- promote anything to Canonical / SSOT
- invent or guess contractor information or credentials
Payment work stops at test environments; researching providers needs no account. Stop only the blocked part and continue independent work.

## Known hazards
- Fake/synthetic data: everything in `sample_case.py`, test photos ("SYNTHETIC PHOTO PLACEHOLDER") and `evidence/` is synthetic. Required-space depths there are NOT specs.
- Approvals in Evidence are `DEV_SIMULATED`. No real Human approval has happened.
- Dev auth token (`HOA_DEV_AUTH=1`) is not real authentication.
- Do not run `playwright install` (no network browser download); use the system Chromium via `executable_path`.
- Do not commit `static/vendor/` (Pyodide binaries), `.venv/`, `data/`.

## PR monitoring policy (instruction from 伊佐; applies to PR srpa10460/n8n#1 and successors)
Goal: watch CI, review comments, merge conflicts and Head updates; act only when needed. Principle: Agent First >> Diagnostic >> Evidence >> Regression Test >> Human Final Review. Merge is ALWAYS a Human Gate.
1. Status check covers: OPEN/CLOSED, Head SHA, mergeable, CI/Actions, reviews, review threads, comments, conflicts.
2. CI/Actions count 0 => record `NO_CI_RUNS`; never treat as PASS; keep it separate from HOMURA verification. The local Evidence of `scripts/run_all_tests.sh` is the source of truth.
3. CI failure => diagnose first and classify: A = caused by this PR; B = upstream n8n / workflow / infrastructure; C = undeterminable. Only A and only low-risk local fixes: fix, test, push. B: change no code. C: do not guess; collect evidence.
4. Review comment => typos, lint, doc fixes, obvious small bugs (no design change) may be handled by the Agent. Anything touching architecture, data model, security, offline design, approval model, billing, authentication, SSOT, external publication or production deployment goes to the Human Gate. Do not assume a reviewer is right: reproduce/verify before acting.
5. Conflict => no automatic merge. Inspect the conflicting files and blast radius. Pulling in changes outside `homura-field-dx/` is a Human Gate. Never make unintended changes to n8n itself.
6. Head SHA changed => do not reuse earlier Evidence for the new Head. Check what changed, re-run the needed regression tests, re-bind Evidence to the new Head SHA.
7. Forbidden: auto-merge; acting as Reviewer approval; production deploy; billing/contract operations; credential changes; SSOT/Canonical promotion; unneeded changes outside `homura-field-dx/`; treating 0 CI runs as PASS.
8. Notify the Human only on: CI failure, review/comment added, conflict, Head SHA change, a design decision needed, security/credential/billing/production matters, merge-ready. No change => no notification.
9. Monitoring writes: do **not** create periodic monitoring commits. On no-change, do **not** write to the repository. Monitoring state/log lives **outside** the repository. `docs/pr_monitor_log.md` is an **historical initial record only** — do not treat it as the live status log, and do not create a commit solely to delete or refresh it.
Report format (Signal / Decision / Reason / Evidence / Next Action / State) with 🟢 READY, 🟡 CAUTION, 🔴 BLOCKED, 🔵 INFO.

## Approval authenticity (F-4 OPEN / Production Gate)
`HUMAN_FINAL` currently records a typed approver name and version+hash binding. It does **not** guarantee authenticated approver identity, approval integrity, or signed / server-verifiable authenticity. Before Production / real customer data / external operation, design and implement: authenticated approver identity, approval integrity, signed or server-verifiable approval record, and manifest authenticity / anti-tamper. Do **not** treat F-4 as PASS.
