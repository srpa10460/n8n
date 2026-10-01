# CHECKPOINT-001

Branch: claude/cool-meitner-1tymfk   Dir: homura-field-dx/

## Done and verified
- Env check; core A domain (units, catalog versions, instances, validation, interference, approval gate, exports, derived Scene)
- 37 unit tests pass (evidence/test_run_verbose.txt); case 1 end-to-end run + Chromium render of plan.svg (preview watermarked / approved clean). One render defect (overlapping labels) found and fixed.

## Not verified / not implemented
- Blender build (blender_build.py unexecuted; Blender absent), section/explode/camera rendering, any video
- Photo-to-draft estimation; general dimension constraints; door-swing interference
- UI of any kind (so no UI screenshots -> PDF manual and PR video cannot start honestly)
- PDF manual (needs implemented UI screenshots), PR video (needs real screen + Blender renders)
- Subscription/payment/VPS design and test-mode payment checks
- Independent Guardian review: not run (no independent reviewer in this session); evidence prepared for it

## BLOCKED / needs Human
- Original text of KC-HAO-HOA-001, SC-HAO-HOAP-001, GC-HAO-OUTCOME-001 not available here
- VPS configuration unknown; no access from this session
- Mina contract/billing details: none invented; no billing, production, or publication action taken

## Next (resume here)
1. Minimal web UI (Vite/vanilla or served HTML) over hoa_field via small HTTP API, so screens exist for manual/video
2. Blender install (sandbox) and execute blender_build.py, render still and turntable, verify with ffmpeg
3. Test-mode payment design (provider choice needs official docs + Isa approval of any account creation)
