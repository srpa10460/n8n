# HOMURA Interior Field DX - 共通仕様 (A / B)

Status: DRAFT working spec for development. Not promoted to any Canonical / SSOT.
Source of every requirement below: the task instructions given by 伊佐 in the originating Claude Code session (2026-10-01), i.e. "HOMURA Interior Field DX: 開発・制作指示", the follow-up "CHECKPOINT-001から続行", the "オフライン現場作業" addition and the handoff request.
NOT used as a source (original text was NOT obtainable: searched the repository, the sandbox filesystem for md/txt/json/pdf containing the IDs, and Google Drive full-text/title search - no hits): KC-HAO-HOA-001, SC-HAO-HOAP-001, GC-HAO-OUTCOME-001. Nothing in this repo is derived from those IDs. If they are supplied later, diff them against this file; do not assume they agree.

## 1. Roles

A: クライアント用 現場アプリ。現場写真・採寸・注記を整理し、作図ドラフト、実測値に基づく2D/3D、PDF、後工程への受け渡しを支援する。
B: HAO用 3D・映像制作アプリ。Aの承認済みデータから Blender モデル、断面、分解表示、カメラワーク、説明映像、PR動画用素材を作る。
Boundary: B only reads A's APPROVED data version. B's presentation scenes are derived and never overwrite A's dimensions, equipment positions or parts. Unapproved data used in a preview must be shown as unapproved.

Other deliverables named in the instructions (status in docs/acceptance_spec.md): PR video for A, professional PDF manual (internal TOC links, bookmarks, UI screenshots, operation steps, troubleshooting), subscription/VPS sales preparation (initial candidate contractor: Mina-san).

## 2. A design principles (from instructions)

- Object Catalog is client-extensible: name, category, measurement items, required/optional, shape template, photo & annotation requirements. Each measurement item states datum point, axis, unit, method, tolerance, source.
- Catalog definition and on-site object instance are separate; definitions are versioned; an instance pins the definition version it was created with, so later definition updates never change the meaning of past cases.
- Measured values are the dimensional source of truth. Photo-derived estimates are distinguished from measured values; missing dimensions are never guessed.
- Units mm / m / inch etc. accepted for input and display; internal canonical unit mm (Decimal, 0.001 mm quantum, exact conversion factors in/ft by definition; floats rejected).
- Flow: photo > draft drawing > measured-value entry/correction > dimension constraints > 2D/3D > Human Review.
- Interference check runs only within defined shape/placement/required-space; anything unchecked is never reported as pass.

## 3. Offline field work (hard requirement added by 伊佐)

1. Projects, catalog, objects, measurements, units, datum, photos, annotations work offline. Catalog needed on site is stored on the device beforehand.
2. Input and photos persist on the device. Distinct states: 端末保存済み / 未送信 / 送信中 / サーバー受領済み / 送信失敗. A failed save is never displayed as saved.
3. Projects and attached photos are restored after app quit/restart. If first-time preparation needs a connection, that is stated in the UI.
4. After reconnect the user presses 送信 (manual). Auto-send is not required now. Per-project progress, failure reason and retry are shown.
5. Stable IDs and versions for project/object/attachment. A cut or resend must not duplicate. "Sent" is declared only after the server's receipt and the attachments are reconciled.
6. If input changes while sending, the sent version and the newer unsent version are distinguished. Conflicts with other devices are never silently overwritten; the diff is shown.
7. Handle low storage, photo save failure, auth expiry. Never auto-delete unsent data. Design device-data protection and recovery export.
8. Delivery technology (PWA etc.) must be chosen by verifying photo persistence, restore after restart and storage limits on the TARGET device. Target device is NOT decided: current choice (PWA + IndexedDB + Service Worker) is an assumption; it must not be reported as passed on any target device.
9. Required scenarios: online prepare > offline start > input/photo > quit/restart > restore > reconnect > send; plus interrupted send, resend, low storage, auth expiry, version conflict.
Cloud-dependent features are labelled 接続後に処理. Priority: offline operate/save/resume first, then sync.

## 4. Interference semantics (implemented; src/hoa_field/interference.py docstring is normative for the formulas)

Three separate questions, never merged:
- OVERLAP: boxes overlap iff penetration > 0 on all three axes; face contact (0) is not overlap and is reported as contact.
- DISTANCE: Euclidean distance between boxes, sqrt(sum(max(0,gap_i)^2)); per-axis gaps shown; status INFO (no pass/fail without a requirement).
- REQUIRED SPACE (work/maintenance/opening): per definition, side, depth_mm and a mandatory `basis` text are client inputs; the system never fills depth from general knowledge. PASS = space free of other solids and inside the room; FAIL = blocked / leaves room; UNCHECKED = no space defined, unconfirmed objects exist, door/drawer object without declared opening envelope, unsupported shape.
Verified cases: evidence/interference_cases.md (21 rows, expected vs actual).

## 5. Data model and versions

Project{project_id, room, data_version (monotonic, +1 per change), status DRAFT/IN_REVIEW/APPROVED, instances, assets, approvals}; ObjectInstance pins definition_id@version; Measurement{mm, source MEASURED|ESTIMATED_PHOTO, original input text}; content_hash = sha256(canonical snapshot) covers measurements, placements, annotations, photo asset sha. Asset id = "A-" + first 12 hex of sha256 (content addressed). Catalog versions append-only.
Approval: bound to (data_version, content_hash); caller must state the version/hash the reviewer saw (stale => refused); FAIL cannot be waived; UNCHECKED needs a reasoned waiver; any later change invalidates the approval. Kinds: DEV_SIMULATED (development test, labelled everywhere) and HUMAN_FINAL (real case, named Human). No real approval has been performed.

## 6. Sync protocol (src/hoa_field/server.py docstring is normative)

begin (server recomputes hash with the SAME core, checks base_rev, stages, lists missing assets) > PUT asset (X-Sha256 verified, atomic) > commit (all assets present+hash, then rev+1; previous rev archived under history/, never deleted). Every step is idempotent. Conflict (base_rev mismatch) => 409 + diff; user chooses adopt-server (local copy backed up on device first) or overwrite (rebase on server rev; server's old rev kept in history). Auth is DEV-ONLY signed short-lived token; real authentication is NOT designed.

## 7. Stop conditions (verbatim intent from the instructions)

Do NOT execute without 伊佐's explicit approval:
- starting billing to Mina-san, enabling any real contract / production subscription
- external publication, general sales start, production deploy
- purchasing paid services, new contracts such as VPS
- deleting production data or irreversible changes to it
- promotion to Canonical / SSOT
Never guess or invent contractor information or credentials. Payment preparation stops at test environment. Stop only the BLOCKED part; continue independent work.
Also: PR video must separate implemented features from concepts and must not state efficiency/accuracy numbers without Evidence. Manuals use screenshots of the implemented UI. A plan or mock is never reported as completed operation/automation.

## 8. Reporting convention (from instructions)

Result first; separate 実装済み / 検証済み / 未検証 / BLOCKED; give save locations, how to run, Evidence, next step; mark Human-decision items with 🔳. Independent Guardian review: perform if an independent reviewer is executable and record it separately from self-verification; otherwise prepare evidence and record "not performed".
