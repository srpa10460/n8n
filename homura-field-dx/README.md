# HOMURA Interior Field DX (dev workspace inside an n8n fork)

Start here: `AGENTS.md` > `checkpoints/CHECKPOINT-002.md` > `docs/SPEC.md`.

Quick start
- unit tests (no deps): `python3 -m unittest discover -s tests -v`
- full env + browser E2E: `./scripts/setup_dev_env.sh && ./scripts/run_all_tests.sh`
- run the app: `HOA_DEV_AUTH=1 PYTHONPATH=src python3 -m hoa_field.server 8765`  -> http://127.0.0.1:8765/
- representative case (headless, no browser): `python3 cases/run_representative.py evidence/case1`

Layout: `src/hoa_field` core+engine+sync server | `static` PWA (offline-first) | `tests` | `docs` (SPEC, acceptance, traceability, screens) | `evidence` | `checkpoints` | `scripts`
Isolated from n8n packages (see docs/n8n_impact_and_migration.md). Python runtime = stdlib only.
