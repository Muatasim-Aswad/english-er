#!/usr/bin/env bash
set -euo pipefail

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

run_step() {
  local label=$1
  shift
  local log_file=$work_dir/step.log
  if "$@" >"$log_file" 2>&1; then
    printf 'PASS %s\n' "$label"
    return
  else
    local status=$?
    printf 'FAIL %s (exit %d); final 120 lines:\n' "$label" "$status" >&2
    tail -n 120 "$log_file" >&2
    exit "$status"
  fi
}

run_step "GitHub workflows" actionlint
run_step "release tooling lint" uv run --offline --frozen --directory apps/backend ruff check ../../scripts/release_check.py ../../scripts/deploy_identity.py ../../scripts/scan-secrets
run_step "release tooling typing" uv run --offline --frozen --directory apps/backend mypy --strict ../../scripts/release_check.py ../../scripts/deploy_identity.py ../../scripts/scan-secrets
run_step "release tooling format" uv run --offline --frozen --directory apps/backend ruff format --check ../../scripts/release_check.py ../../scripts/deploy_identity.py ../../scripts/scan-secrets
run_step "application boundaries" python3 scripts/check_boundaries.py
run_step "Python lockfile" uv lock --offline --directory apps/backend --check
run_step "pnpm lockfile" pnpm install --lockfile-only --frozen-lockfile --ignore-scripts
run_step "formatting" pnpm exec vp fmt --check
run_step "boundary checker lint" uv run --offline --frozen --directory apps/backend ruff check ../../scripts/check_boundaries.py
run_step "boundary checker format" uv run --offline --frozen --directory apps/backend ruff format --check ../../scripts/check_boundaries.py
run_step "boundary checker typing" uv run --offline --frozen --directory apps/backend mypy --strict ../../scripts/check_boundaries.py
run_step "Python lint" uv run --offline --frozen --directory apps/backend ruff check src tests scripts
run_step "Python format" uv run --offline --frozen --directory apps/backend ruff format --check src tests scripts
run_step "Python strict typing" uv run --offline --frozen --directory apps/backend mypy
run_step "backend unit and integration tests" uv run --offline --frozen --directory apps/backend pytest -q
run_step "frontend lint" pnpm --filter @english-er/web exec vp lint
run_step "frontend strict typing" pnpm --filter @english-er/web exec tsc -b
run_step "frontend tests" pnpm --filter @english-er/web exec vp test run
run_step "OpenAPI drift" bash scripts/api-types.sh --check
run_step "production web build" pnpm run build:all
run_step "capture latency" python3 integrations/voxtype/benchmark.py
run_step "Playwright review flow" bash scripts/run_e2e.sh
run_step "production UI/API serving" python3 scripts/production_smoke.py
