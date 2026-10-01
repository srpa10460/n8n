# PR video for A - storyboard (PLAN ONLY; no video of the app has been produced yet)

Rule: show only what is implemented AND verified (acceptance_spec.md VERIFIED-AUTO). No efficiency/accuracy numbers (no Evidence exists). Concepts are labelled as concepts. Flow requested: 現場の課題 >> 操作 >> 成果物 >> 後工程への受け渡し, with real screens and real generated outputs.

| # | Beat | Visual source (exists?) | Claim allowed | Claim NOT allowed |
|---|------|--------------------------|---------------|-------------------|
| 1 | 現場の課題: 電波のない現場で採寸・写真が散らばる | narration only / owner-shot site footage (does not exist) | qualitative problem statement by 伊佐 | any time-saving number |
| 2 | 事前準備: オンラインでCatalogを端末に保存 | docs/screens/10b_prepare_state_online.png (real) | prerequisite: first online preparation | "just works anywhere" |
| 3 | 操作(オフライン): 案件 > 対象物 > 寸法(単位換算) > 写真・注記 | docs/screens 09,11a,11,12 (real stills); live screen recording NOT yet made (scripts/record needed) | works offline in Chromium | verified on tablets |
| 4 | 実測と推定の区別 / 未確認は合格にしない | screens 11 (legend), 13a (check) | measured vs estimate vs missing shown | automatic drawing from photos (NOT implemented) |
| 5 | 再起動後の復元 | docs/screens/16_restored_after_restart.png | restored after app restart (Chromium test) | guaranteed on every device |
| 6 | 成果物: 作図プレビュー・出力(SVG/OBJ/manifest) | screens 13, 14b; evidence/case1/approved/* (real files) | outputs generated on device, versioned, hash-bound | PDF drawing output (not built) |
| 7 | レビュー・承認 | screens 14a,14 (dev-simulated approval) | approval bound to a data version | real-case approval has occurred |
| 8 | 後工程への受け渡し(B): 承認済みデータからBlenderモデル、周回 | evidence/blender/orbit.mp4 + still.png (real render; plain boxes) | model generated from approved data with dimension/placement/hash checks | production-quality visuals, sections/exploded video (only one derived still exists) |
| 9 | 送信: 接続復帰後に手動送信、受領確認 | screens 17, 19 | manual send with receipt check | automatic sync |
| 10 | 注意書き: 開発版・合成データ・対象端末未検証 | text card | - | - |

Production steps remaining: record the live UI with real timing (Playwright video or screen capture), re-render Blender with presentation-grade materials/camera, voice-over script by 伊佐 (skills/guardian policy for AI-generated media apply - not assessed here), edit, render, QA frames. Final cut waits for 伊佐's content decisions.
