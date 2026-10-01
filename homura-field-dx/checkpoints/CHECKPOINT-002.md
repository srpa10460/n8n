# CHECKPOINT-002  (supersedes CHECKPOINT-001; read AGENTS.md first)

## Where
- Repo: srpa10460/n8n (upstream n8n fork). Branch: `claude/cool-meitner-1tymfk` (pushed). Project dir: `homura-field-dx/`. PR: https://github.com/srpa10460/n8n/pull/1 (created from the Claude Code UI; pushing to the branch updates it). Note: it targets the n8n fork, so n8n's general PR checks run on it; nothing in this dir is part of n8n.
- Commits on the branch after upstream base 96d3faf3: 3287cb36 (core, CHECKPOINT-001) > a9c7d7a5 (offline-first PWA, sync, interference redesign) > a6999f73 (handoff docs) > the final commit of this checkpoint (B, manual, billing sim, docs; `git log --oneline -6`).
- Files outside `homura-field-dx/` changed vs base: 0 (see docs/n8n_impact_and_migration.md; migration is only a proposal, not executed).

## Done and VERIFIED (automated, this sandbox only: Linux, Chromium 141 headless, Python 3.11)
- Core + engine: units, versioned Catalog, validation, approval (version+hash bound), exports, derived Scene. Interference split into overlap / distance / required space (21 expected-vs-actual rows: evidence/interference_cases.md).
- Browser app (offline-first PWA; domain logic = the Python core running in the browser via Pyodide 0.27.7, same code as the server): all of project/catalog/object/placement/dims/units/photos/annotations/validation/preview/review/export works offline; persisted in IndexedDB; restored after restart. Manual sync with 5 visible states, conflict diff, backup export/import. `tests/e2e_offline.py`: 41/41 checks (offline boot, restart restore incl. photos, send, interrupted upload + retry w/o duplicates, edit-while-sending, auth expiry, version conflict, quota fault injection, backup import into a fresh profile). Screens: docs/screens/*.png.
- B: `blender_build.py` executed with bpy 5.0.1: model built from the approved export only; 11 checks (dimensions and placement vs snapshot, hash, derived scene leaves base untouched, sources unchanged, mp4 encoded); refuses unapproved/tampered input (tests/test_blender_guards.py). Outputs in evidence/blender (still, derived still, 3 s 72-frame orbit mp4, model.blend, report) - inspected visually; the first render had bad framing and was fixed.
- Manual: docs/manual/HOA_Field_DX_Manual.pdf (29 pages; TOC links, bookmarks, real UI screenshots, operation steps, troubleshooting). `scripts/qa_manual.py` 18 checks + rendered pages inspected (a doubled TOC numbering defect was found and fixed).
- Billing preparation: provider-neutral entitlement simulation (duplicate / out-of-order / failure / recovery / stale / cancel) 9 tests.
- 58 unit tests pass (`evidence/test_run_verbose.txt`).
- Defects found only by running/rendering and fixed: overlapping plan labels; unclosed function in the UI; server global lock stalling static serving; same photo silently re-tagged; stale-message races in the UI; stale sync state after conflict action; spec "source" shadowed by measurement source in the UI; TOC numbering; Blender framing.

## NOT verified / NOT implemented
- Any TARGET device (undecided): persistence, quota, eviction, restart behaviour on tablets/iOS Safari/Android Chrome (OFF-8). Quota exhaustion was fault-injected, not a real full disk. Second device in conflict tests was simulated by another client id.
- HTTPS/VPS deployment; real authentication (dev-only HMAC token). Service Worker needs localhost/HTTPS.
- Photo->auto-draft, dimension constraints, door-swing/non-box interference, fractional-inch input.
- B quality: plain Workbench boxes; no section view, camera-work design, materials. PR video: storyboard only (docs/pr_video/storyboard.md), no video, no live UI recording.
- Payment: provider facts are second-hand (direct fetch of official sites blocked by the sandbox proxy; search summaries of official pages). No test-mode provider integration, no account. Pricing = formula/structure only, no prices (inputs missing).
- Does root-level n8n `pnpm lint/format` (biome) touch this dir? Not run.
- Independent Guardian review: NOT performed (no independent reviewer in session). Evidence and docs/TRACEABILITY.md are prepared for one.

## BLOCKED (needs Human / outside session)
- KC-HAO-HOA-001, SC-HAO-HOAP-001, GC-HAO-OUTCOME-001: not found (repo, sandbox filesystem md/txt/json/pdf, Google Drive search). Spec uses only the instruction text.
- Target device list; VPS config/access and HTTPS plan; real auth scheme; destination repo for migration.
- Real object catalog and required-space values from the client (INT-4); synthetic values are labelled as such.
- Pricing inputs: VPS cost, expected customers/photo volume, support scope, margin, grace days, provider choice, Mina-san's contractor details (never inferred).
- Stop conditions (AGENTS.md): billing Mina-san, real contract, external publication, paid purchases, production deploy, SSOT promotion - none was done.

## Local-only / environment dependencies (NOT in git)
- `static/vendor/pyodide/` (git-ignored, 14 MB): `./scripts/fetch_pyodide.sh` (npm pyodide@0.27.7).
- Python venv: playwright 1.63.0, pymupdf 1.28.2, pypdf 6.19.0, reportlab 5.0.1, bpy 5.0.1. This session's: `/tmp/claude-0/bl/v` (ephemeral). Recreate: `./scripts/setup_dev_env.sh` (requirements-dev.txt).
- OS packages installed with apt for bpy: libegl1 libgl1 libxkbcommon0 libsm6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libgomp1 (needed again on a fresh container). EGL warnings during render are benign (no GPU).
- System Chromium 141 at /opt/pw-browsers/chromium-1194/chrome-linux/chrome (override `HOA_CHROME`; never run `playwright install`). Also used: node 22, ffmpeg (libx264), poppler-utils (pdftoppm/pdftotext/pdfimages/pdffonts), IPAGothic font (manual PDF renders Japanese with it).
- Network needed once for pip/npm/apt. Runtime data (`data/`, temp browser profiles) is not kept; Evidence copies are committed.
- Large binary evidence committed: evidence/blender/model.blend, orbit.mp4, docs/screens/*.png, evidence/e2e_offline/ (synthetic photos).

## Next (resume here, in order)
1. Decide with 伊佐 (🔳): target device list, VPS/HTTPS plan. Then run OFF-8 on the real device (photo persistence, restart restore, quota) and HTTPS dev deployment test.
2. VID-1: record live UI (Playwright video/screen capture) of the verified flow; presentation-grade Blender re-render (materials, camera, a section view as a derived scene); assemble per docs/pr_video/storyboard.md; QA frames. Apply the YouTube/AI media policy skills available to the owner before any AI-generated media (not assessed here).
3. FLOW-2/CON-1: design photo-assisted drafting and dimension constraints (not started). INT-4: obtain real objects/spaces and re-run the case table.
4. PAY-1: with approval, re-verify provider facts on the live official pages, pick one provider, set up TEST mode only, implement webhook = trigger + authoritative fetch per billing_sim.py; fill pricing inputs.
5. Independent Guardian review when a reviewer is available.
6. Migration out of the n8n fork per docs/n8n_impact_and_migration.md after a destination is chosen.

🔳 Human decisions pending: target devices; VPS/HTTPS; migration destination; real catalog + required-space inputs; whether to supply the three normative documents; payment provider + pricing inputs; grace-days policy.
