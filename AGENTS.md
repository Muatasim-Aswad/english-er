# Project instructions

Read [Development](docs/DEVELOPMENT.md) and [Architecture](docs/ARCHITECTURE.md) before changes. Follow [Operations](docs/OPERATIONS.md) for installation, migration, and live-state boundaries.

Run `scripts/verify-task check` before handoff. Regenerate both HTTP artifacts with `mise run api:generate`; never edit generated types by hand. Keep feature imports within their public APIs. Do not stage ignored `docs/plans/` state or run live model/capture checks as part of normal verification.

Releases are source-only: versioned Git tags and release notes, without custom bundles or downloadable build artifacts. Follow [Releasing](docs/RELEASING.md).
