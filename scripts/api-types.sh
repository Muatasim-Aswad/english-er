#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || (${1:-} != "" && ${1:-} != "--check") ]]; then
  printf 'usage: %s [--check]\n' "$0" >&2
  exit 64
fi

mode=${1:-generate}
openapi_target=apps/backend/openapi.json
target=apps/web/src/infra/schema.ts
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

uv run --offline --frozen --directory apps/backend python scripts/dump_openapi.py >"$work_dir/openapi.json"
pnpm --filter @english-er/web exec openapi-typescript "$work_dir/openapi.json" --output "$work_dir/schema.ts"

if [[ $mode == "--check" ]]; then
  if ! cmp -s "$work_dir/openapi.json" "$openapi_target"; then
    printf '%s is stale; run mise run api:generate\n' "$openapi_target" >&2
    exit 1
  fi
  if ! cmp -s "$work_dir/schema.ts" "$target"; then
    printf '%s is stale; run mise run api:generate\n' "$target" >&2
    diff -u "$target" "$work_dir/schema.ts" || true
    exit 1
  fi
  printf 'API contract is current\n'
  exit 0
fi

install -m 0644 "$work_dir/openapi.json" "$openapi_target"
install -m 0644 "$work_dir/schema.ts" "$target"
printf 'Generated %s\n' "$target"
