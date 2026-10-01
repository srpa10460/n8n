# Acceptance table (authoritative status; update with every checkpoint)

Legend: VERIFIED-AUTO = automated test passes in THIS environment (Linux, headless Chromium 141, Python 3.11) | PARTIAL | NOT-IMPLEMENTED | NOT-EXECUTED | NOT-PERFORMED | BLOCKED | UNVERIFIED-TARGET = needs the real target device.
Requirement text: docs/SPEC.md. Code/test/evidence mapping: docs/TRACEABILITY.md. Last updated: CHECKPOINT-002.

| ID | Requirement (short) | Status | Notes |
|----|---------------------|--------|-------|
| CAT-1 | Client-addable Object Catalog with datum/axis/unit/method/tolerance/source | VERIFIED-AUTO | unit + browser form |
| CAT-2 | Definition/instance separation, version pinning | VERIFIED-AUTO | UI badge "新版あり" exists but not asserted in E2E |
| UNIT-1 | mm/cm/m/in/ft input, canonical mm Decimal | VERIFIED-AUTO | fractional inch "1/2" not supported |
| MEAS-1 | Measured vs photo-estimated vs missing distinguished; estimates never confirmed; no guessing | VERIFIED-AUTO | |
| FLOW-1 | photo attach + annotation as evidence | VERIFIED-AUTO | |
| FLOW-2 | Photo -> automatic draft drawing | NOT-IMPLEMENTED | UI says so explicitly |
| CON-1 | Dimension constraints (e.g. fit-in-opening) | NOT-IMPLEMENTED | only min/max range validation exists |
| INT-1 | Overlap / distance / required space separated | VERIFIED-AUTO | evidence/interference_cases.md |
| INT-2 | Required space depth+basis are inputs; undefined => UNCHECKED | VERIFIED-AUTO | sample values are SYNTHETIC |
| INT-3 | Non-box shapes, unmodelled opening ranges shown UNCHECKED | VERIFIED-AUTO | non-box cannot even be registered |
| INT-4 | Real-world adequacy of the box/axis-aligned model | BLOCKED | needs Isa to supply real objects + spaces; no abstract approval requested |
| APR-1 | Approval bound to version+hash; stale refused; change invalidates | VERIFIED-AUTO | |
| APR-2 | DEV_SIMULATED vs HUMAN_FINAL distinguished everywhere | VERIFIED-AUTO | HUMAN_FINAL never exercised by a real Human |
| AB-1 | Project/Object/Asset IDs + data/approved version tracked in outputs | VERIFIED-AUTO | manifest.json |
| AB-2 | Derived Scene never overwrites source; unapproved preview marked | VERIFIED-AUTO | data layer only (no Blender yet) |
| OFF-1 | Offline: project/catalog/object/measure/unit/datum/photo/annotation | VERIFIED-AUTO | Chromium only |
| OFF-2 | Persistent device save; 5 states shown; save failure never shown as saved | VERIFIED-AUTO | quota by fault injection, not real disk-full |
| OFF-3 | Restore after quit/restart incl. photos; first-time online prerequisite stated | VERIFIED-AUTO | context close+relaunch with same profile |
| OFF-4 | Manual send, per-project progress/failure reason/retry | VERIFIED-AUTO | auto-send not implemented (not required) |
| OFF-5 | Stable IDs/versions; no duplicates on cut/resend; "received" only after reconciliation | VERIFIED-AUTO | |
| OFF-6 | Sent version vs newer unsent shown; conflict diff, no silent overwrite | VERIFIED-AUTO | conflict = another client id on same server; true multi-device not tested |
| OFF-7 | Low storage, photo save failure, auth expiry handled; no auto-delete; recovery export/import | VERIFIED-AUTO | auth is DEV-ONLY token |
| OFF-8 | Delivery technology validated on TARGET device | UNVERIFIED-TARGET | target device undecided; PWA is an assumption |
| OFF-9 | Required scenario chain incl. interrupt/resend/quota/auth/conflict | VERIFIED-AUTO | tests/e2e_offline.py (41 checks) |
| OFF-10 | Real HTTPS/VPS deployment (Service Worker needs secure context off localhost) | BLOCKED | VPS unknown/unavailable |
| B-1 | Blender model from approved data, dims/placement/hash check | NOT-EXECUTED | bpy 5.0.1 installs from PyPI; script exists, not yet run (see CHECKPOINT) |
| B-2 | Still image + short orbit video, visual inspection | NOT-EXECUTED | |
| DOC-1 | PDF manual with TOC links, bookmarks, UI screenshots, render QA | NOT-EXECUTED | UI screenshots exist in docs/screens |
| VID-1 | PR video storyboard / production | NOT-EXECUTED | |
| PAY-1 | Payment providers comparison (official sources), pricing draft | NOT-EXECUTED | no accounts to be created |
| GRD-1 | Independent Guardian review | NOT-PERFORMED | no independent reviewer available in session; evidence is ready |
