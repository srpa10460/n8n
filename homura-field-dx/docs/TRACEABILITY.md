# Traceability: requirement -> code -> test -> evidence

Paths relative to project root `homura-field-dx/`. "E2E:" names are the `check(...)` labels in tests/e2e_offline.py (results in evidence/e2e_offline/results.json).

| ID | Code | Test | Evidence |
|----|------|------|----------|
| CAT-1,2 | src/hoa_field/catalog.py, sample_case.py | tests/test_core.py Catalog_; E2E: catalog stored on device before going offline | evidence/e2e_offline/results.json, docs/screens/10_catalog_prepared_online.png |
| UNIT-1 | src/hoa_field/units.py | tests/test_core.py Units; E2E: 30 in -> 762.000 mm | evidence/test_run_verbose.txt |
| MEAS-1 | project.py dimension_status, validate | Validation.test_estimate_never_confirmed; E2E: estimate labelled 写真推定 | docs/screens/11_offline_dims.png |
| FLOW-1 | engine.py add_photo, annotate; static/app.js V.photos | PhotoRules; E2E: restart: 5 attached photos restored | docs/screens/12_offline_photos.png |
| INT-1..3 | src/hoa_field/interference.py | tests/test_interference_cases.py (writes evidence/interference_cases.md), Interference | evidence/interference_cases.md |
| APR-1,2 | project.py approve/review_items/current_approval; engine.py approve | Approval, ApprovalBinding; E2E: dev-simulated approval labelled | docs/screens/14_offline_approved.png |
| AB-1 | export.py manifest/export_files | Outputs; E2E: offline export manifest approved + hash | evidence/case1/approved/manifest.json |
| AB-2 | scene.py | SceneTests | - |
| OFF-1 | static/app.js, bridge.js (Pyodide runs src/hoa_field/engine.py), db.js, sw.js | E2E: offline boot from cache; estimate/unit checks | docs/screens/11..14 |
| OFF-2 | static/db.js writeAll (resolves only on tx.oncomplete); app.js persist/saveBadge/syncBadges | E2E: quota: 保存失敗 shown...; status: 端末保存済み + 未送信 | docs/screens/22_save_failed_quota.png, 15_offline_sync_pending.png |
| OFF-3 | db.js; sync.js interruptedToFailed | E2E: restart: project restored / photos restored / measurement restored / approval still current | docs/screens/16_restored_after_restart.png |
| OFF-4 | static/sync.js send; app.js V.sync | E2E: no auto-send; server received: rev1; sync button disabled offline | docs/screens/17_synced.png |
| OFF-5 | src/hoa_field/server.py begin/put_asset/commit; sync.js | E2E: cut during upload x3; retry: rev2 exactly once; replayed commit is idempotent | docs/screens/18_send_failed_interrupted.png |
| OFF-6 | sync.js adoptServer/rebaseForOverwrite; src/hoa_field/diff.py; server.py conflict | E2E: edit during send; conflict: diff shows both values; override; adopt | docs/screens/19_edit_while_sending.png, 21_conflict_diff.png |
| OFF-7 | db.js; sync.js export/importBackup; server.py token | E2E: auth expired; quota x4; backup file written; import ... new profile | docs/screens/20_auth_expired.png, 23_backup_imported.png |
| OFF-9 | tests/e2e_offline.py | whole file | evidence/e2e_offline/results.json |

Un-mapped (no code/test yet): OFF-8, OFF-10, B-1, B-2, DOC-1, VID-1, PAY-1, GRD-1, FLOW-2, CON-1, INT-4.
