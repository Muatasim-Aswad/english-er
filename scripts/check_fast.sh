#!/usr/bin/env bash
set -euo pipefail
python3 scripts/check_boundaries.py
uv run --offline --frozen --directory apps/backend ruff check ../../scripts/check_boundaries.py
uv run --offline --frozen --directory apps/backend ruff format --check ../../scripts/check_boundaries.py
uv run --offline --frozen --directory apps/backend mypy --strict ../../scripts/check_boundaries.py
pnpm exec vp fmt --check
uv run --offline --frozen --directory apps/backend ruff check src tests scripts
uv run --offline --frozen --directory apps/backend ruff format --check src tests scripts
uv run --offline --frozen --directory apps/backend mypy
pnpm --filter @english-er/web exec vp lint
pnpm --filter @english-er/web exec tsc -b
bash scripts/api-types.sh --check

actionlint
