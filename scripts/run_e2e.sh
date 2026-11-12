#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "$0")/.." && pwd)
e2e_root=$(mktemp -d)
trap 'rm -rf "$e2e_root"' EXIT

export ENGLISH_ER_E2E_ROOT=$e2e_root
export XDG_DATA_HOME=$e2e_root/data
export XDG_STATE_HOME=$e2e_root/state
cd "$repository_root"
pnpm --filter @english-er/web exec playwright test --config playwright.config.ts
