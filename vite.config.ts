import { defineConfig } from "vite-plus";

export default defineConfig({
  fmt: {
    ignorePatterns: ["apps/backend/**", "**/*.md", "apps/web/src/infra/schema.ts"],
  },
  lint: {
    plugins: ["typescript", "oxc"],
    options: {
      typeAware: true,
      typeCheck: true,
    },
    overrides: [
      {
        files: ["apps/web/**"],
        plugins: ["typescript", "oxc", "react"],
        rules: {
          "react/only-export-components": ["warn", { allowConstantExport: true }],
          "react/rules-of-hooks": "error",
        },
      },
    ],
  },
  run: {
    tasks: {
      lint: { command: "vp run -r --cache lint" },
      typecheck: { command: "vp run -r --cache typecheck" },
      test: { command: "vp run -r --cache test" },
      build: { command: "vp run -r --cache build" },
      "fmt:check": { command: "vp fmt --check" },
      "py:format": {
        command: "uv run --directory apps/backend ruff format --check",
        input: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.ruff_cache/**"],
        output: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.ruff_cache/**"],
      },
      "py:lint": {
        command: "uv run --directory apps/backend ruff check",
        input: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.ruff_cache/**"],
        output: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.ruff_cache/**"],
      },
      "py:typecheck": {
        command: "uv run --directory apps/backend mypy",
        input: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.mypy_cache/**"],
        output: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/.mypy_cache/**"],
      },
      "py:test": {
        command: "uv run --directory apps/backend pytest -q",
        input: [
          { auto: true },
          "!apps/backend/.venv/**",
          "!apps/backend/.pytest_cache/**",
          "!apps/backend/**/__pycache__/**",
        ],
        output: [
          { auto: true },
          "!apps/backend/.venv/**",
          "!apps/backend/.pytest_cache/**",
          "!apps/backend/**/__pycache__/**",
        ],
      },
      "py:build": {
        command: "uv build --directory apps/backend",
        input: [
          { auto: true },
          "!apps/backend/.venv/**",
          "!apps/backend/dist/**",
          "!apps/backend/**/__pycache__/**",
        ],
        output: ["apps/backend/dist/**"],
      },
      "api:check": {
        command: "bash scripts/api-types.sh --check",
        input: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/**/__pycache__/**"],
        output: [{ auto: true }, "!apps/backend/.venv/**", "!apps/backend/**/__pycache__/**"],
      },
      "lock:python": {
        command: "uv lock --directory apps/backend --check",
      },
      "lock:pnpm": {
        command: "pnpm install --lockfile-only --frozen-lockfile --ignore-scripts",
      },
      foundation: {
        command: [
          "vp run fmt:check",
          "vp run lint",
          "vp run typecheck",
          "vp run test",
          "vp run build",
          "vp run py:format",
          "vp run py:lint",
          "vp run py:typecheck",
          "vp run py:test",
          "vp run py:build",
          "vp run api:check",
          "vp run lock:python",
          "vp run lock:pnpm",
        ],
      },
    },
  },
});
