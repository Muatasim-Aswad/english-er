# Development

This document owns setup, checks, coding conventions, and generated artifacts. [Architecture](ARCHITECTURE.md) owns boundaries and invariants; [Operations](OPERATIONS.md) owns installation and deployment.

## Setup

Run from the repository root:

```bash
mise install
uv sync --directory apps/backend --frozen
pnpm install --frozen-lockfile
pnpm --filter @english-er/web exec playwright install chromium
mise run hooks:install
```

Mise owns the pinned toolchain; interpreter selectors and `package.json` must agree. Workspace JavaScript versions live in `pnpm-workspace.yaml`; `uv.lock` and `pnpm-lock.yaml` own resolutions. Python remains pinned to the supported Kokoro/CUDA runtime. TypeScript stays within `openapi-typescript`'s declared peer range.

The default Python groups include development tools and GPU speech dependencies. CPU-only verification excludes speech with `UV_NO_GROUP=speech`; CI uses that setting with the same frozen lockfile and gate. Speech tests use fake synthesis and do not download a model or require a GPU. To prepare actual installed speech while network/GPU access is available:

```bash
mise run speech:prepare
```

## Checks and hooks

```bash
scripts/verify-task check
```

This is the full local and CI gate: boundaries, locks, formatting, lint, strict typing, backend/frontend tests, generated-contract drift, production build, capture latency, Playwright, and production serving. It prints one success line or bounded failure output. Tests use disposable databases/state, a fake provider, and loopback port 8765; they do not modify live capture or services.

`hooks:install` enables committed `.githooks`: pre-commit runs `check:fast`; pre-push runs the full gate. GitHub Actions runs the same full gate on pushes and pull requests. Hooks never commit or push. Use `git config --unset core.hooksPath` to disable this checkout's hook configuration.

| Task | Purpose |
| --- | --- |
| `check:fast` | Commit-time format, lint, types, boundaries, and contract checks |
| `check:boundaries` | Import layers, feature APIs, and dependency cycles |
| `check:foundation` | Cached foundation checks and builds |
| `check:capture`, `check:worker`, `check:web`, `check:api` | Focused component checks |
| `api:generate`, `api:check` | Refresh or verify both committed HTTP artifacts |
| `dev:web`, `dev:api`, `dev:worker` | Local development entrypoints |
| `local:install`, `local:deploy` | Explicit operational tasks; see Operations |

Focused Python commands use `uv run --offline --frozen --directory apps/backend`; web checks use `pnpm --filter @english-er/web exec vp <command>`.

## Code and ownership

Follow the ownership and import rules in Architecture. Keep services independent of HTTP and inject ordinary typed dependencies. Put substantial independent React behavior in focused hooks/components beside its feature; pure mappings remain ordinary functions. Extract for coherent responsibilities, not arbitrary file lengths. Favor guard clauses and short error/resource scopes over deep nesting. Comments explain non-obvious constraints only.

Tailwind v4 owns component styling. Tokens live in `apps/web/src/styles.css` under `@theme`; global defaults use `@layer base`. Reuse `shared/ui` primitives, use explicit variant maps, and reserve custom CSS for base/theme rules or specialized behavior. Tests select roles, labels, and `data-*` state rather than styling classes.

Keep display copy in its feature's typed `copy.ts`, shell copy in `app`, and genuinely shared messages in `shared`. Use whole message functions for runtime values. Formatting lives in `infra/format.ts`, configured by `config.ts`; protocol timestamps remain UTC. Preserve API error codes through transport and map them to feature messages. Do not introduce placeholder translation APIs or duplicate generated DTOs.

## Generated HTTP artifacts

Feature routes and DTOs plus platform error schemas are authoritative. `apps/backend/scripts/dump_openapi.py` constructs the schema without opening the database, creating state, or starting a server. `scripts/api-types.sh` is the sole writer of both tracked outputs:

- `apps/backend/openapi.json`
- `apps/web/src/infra/schema.ts`

```bash
mise run api:generate
mise run api:check
```

Update endpoints, schemas, frontend adapters, fixtures, and contract tests together. Verification compares both outputs with fresh generation. The web app consumes generated `paths` through `openapi-fetch`.

## Development and live state

Vite binds to loopback and proxies `/api` to the local backend; its configuration owns the ports and optional `VITE_SERVER_URL` override. Production serves the built frontend through FastAPI.

Normal checks never invoke real Codex, enable capture, edit Voxtype settings, install units, or restart services. Live Codex/Voxtype/GPU checks require explicit operator approval and follow Operations; they are not automated tasks. Keep local state untracked, repository prose unwrapped, and each topic in its authoritative document.

## Source-only releases and security checks

[Releasing](RELEASING.md) owns tags, release notes, and build identity. `scripts/scan-secrets` scans the current Git revision and tracked source with redacted Gitleaks output; CI scans each push/PR range. Dependabot groups updates per ecosystem with a seven-day version cooldown; GitHub security updates bypass version cooldowns.
