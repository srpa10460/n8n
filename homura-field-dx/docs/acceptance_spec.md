# Acceptance spec (dev, A core) - status as of this checkpoint

Source of requirements: the task instruction text only. KC-HAO-HOA-001 / SC-HAO-HOAP-001 / GC-HAO-OUTCOME-001 originals were NOT available in this environment; nothing below is derived from their IDs.

| ID | Requirement | Verification | Status |
|----|-------------|--------------|--------|
| A1 | Client-addable Object Catalog (name, category, dims, required/optional, shape template, photo/annotation requirements, datum/axis/unit/method/tolerance/source) | test_core Catalog_ | VERIFIED (unit) |
| A2 | Catalog definition vs instance separated; version pinned | test_version_pinning_survives_catalog_update | VERIFIED |
| A3 | Measured value is source of truth; photo estimates distinct, never confirmed | test_estimate_never_confirmed | VERIFIED |
| A4 | Unit input mm/cm/m/in/ft, internal mm Decimal, 0.001 mm quantum, float rejected | Units tests | VERIFIED (fractional inch "1/2" not supported) |
| A5 | Flow photo > draft > measurement > constraint > 2D/3D > Human Review | partial: photo registry + annotations + measurement + validation + 2D/3D + review gate | PARTIAL: photo-to-draft estimation NOT implemented; general dimension constraints (e.g. fit-in-opening) NOT implemented beyond range check |
| A6 | Interference only within defined scope; unchecked is never PASS | Interference tests | VERIFIED for box shapes; door swing / non-box NOT covered |
| AB1 | Project/Object/Asset ID, data version, approved version tracked | manifest.json | VERIFIED |
| AB2 | Edit after approval invalidates approval | test_change_after_approval_invalidates | VERIFIED |
| AB3 | Scene derived from approved data, never overwrites source; preview marked | SceneTests | VERIFIED (data layer only) |
| B1 | Blender model generation | blender_build.py written | NOT EXECUTED (Blender absent) |
| T1 | Export failure / rerun | test_export_failure_then_rerun_idempotent | VERIFIED |

Interference semantics note: gap = max axis separation (Chebyshev-style); clearance compared against that. Conservative-vs-lenient behaviour for diagonal neighbours is a design assumption to confirm.
Approval in evidence/ is SIMULATED (dev test); no real Human review occurred.
