# Placement inside upstream n8n: impact check and migration proposal

Facts (verified at commit a9c7d7a5 on claude/cool-meitner-1tymfk):
- `git diff --name-only 96d3faf3 HEAD` outside `homura-field-dx/`: 0 files. n8n source, lockfile, package.json, turbo.json, CI workflows are untouched.
- pnpm-workspace.yaml globs (`packages/*`, `packages/@n8n/*`, `packages/frontend/**`, `packages/extensions/**`, `cypress`, `packages/testing/**`) do not include `homura-field-dx`, so pnpm/turbo ignore it. No dependency on any n8n package; no n8n package depends on it.
- Runtime is Python stdlib only; browser code is plain ES modules; no npm dependency is added.
- lefthook pre-commit globs are `packages/**/...` only (not triggered by this directory).
- CI: 41 workflow files; `grep -L paths` shows several run without path filters (e.g. check-pr-title). A PR from this branch would therefore run n8n's general PR checks; none of them reference this directory. Whether root-level `pnpm lint/format` (biome, no ignore entry for this dir) would pick up `static/*.js` was NOT run: UNVERIFIED. If it does, add the dir to biome ignore in the migrated repo, not in n8n.
- Large/vendored binaries are NOT committed: `static/vendor/` (Pyodide, ~14 MB) is git-ignored; recreate with `scripts/fetch_pyodide.sh`.

Risk of staying in upstream n8n: n8n's license/contribution terms apply to this fork's contents; branch could be mixed into n8n PRs by accident; n8n tooling churn. (License implications were NOT analysed.)

Proposal (NOT executed; destination NOT decided - do not guess one):
1. Decide a destination repository (伊佐). 2. Export history-preserving: `git subtree split -P homura-field-dx -b hoa-split` (or `git filter-repo --subdirectory-filter homura-field-dx` on a clone). 3. Push to the new repo; keep this directory until the new repo passes `scripts/run_all_tests.sh`. 4. Only then remove the directory from the n8n fork via a normal commit (no history rewrite).
Paths in docs are relative to the project root, so the move needs no edits except the CHECKPOINT branch/commit fields.
