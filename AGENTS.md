# AGENTS.md

## Cursor Cloud specific instructions

### Overview

n8n is a TypeScript monorepo (pnpm workspaces + Turbo) with a Node.js/Express backend, Vue 3 frontend, and 400+ integration nodes. See `CLAUDE.md` for full project overview, commands, and coding guidelines.

### Running the application

- **Backend**: `./packages/cli/bin/n8n start` (port 5678, uses SQLite by default). The first visit to `http://localhost:5678` triggers owner account setup.
- **Full dev mode with hot-reload**: `pnpm dev` (Turbo runs all packages in parallel watch mode). Note: Turbo's `--parallel` output may not flush to file when redirected; prefer running in a PTY or start backend/frontend separately.
- **Frontend only** (Vite dev server, port 8080): `pnpm dev:fe:editor`
- **Backend only** (no frontend): `pnpm dev:be`

### Gotchas

- `pnpm build` must complete before `pnpm start` or `./packages/cli/bin/n8n start` will work (the CLI loads compiled JS from `dist/`).
- `pnpm dev` output can appear frozen when redirected to a file due to Turbo's terminal UI buffering. If you need log output, start the backend (`./packages/cli/bin/n8n start`) and frontend (`pnpm dev:fe:editor`) in separate terminals instead.
- The environment variable `N8N_DIAGNOSTICS_ENABLED=false` suppresses telemetry checks at startup.
- Pre-existing test failures exist in `packages/core` (HttpsAgent options mismatch) and `packages/frontend/editor-ui` (date formatting locale issue) — these are not environment problems.

### Testing

- Run tests from within the specific package directory: `cd packages/<pkg> && pnpm test`
- `packages/workflow`: vitest — fast, all passing
- `packages/core`: jest — 67/68 suites pass (2 pre-existing failures)
- `packages/frontend/editor-ui`: vitest — 410/411 suites pass (1 pre-existing date formatting failure)
- Full test suite: `pnpm test` from repo root (runs via Turbo across all packages)

### Lint & Typecheck

- `pnpm lint` from repo root (Turbo orchestrates across all packages)
- `pnpm typecheck` from repo root
- Per-package: `cd packages/<pkg> && pnpm lint`
- Git hooks (lefthook): pre-commit runs biome, prettier, and stylelint on staged files

### Database

SQLite is the default (no external DB needed). PostgreSQL is required for queue mode, multi-main, and container-based Playwright E2E tests but not for standard dev or unit tests.
