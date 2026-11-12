import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite-plus";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const buildIdentity = execFileSync(
  "uv",
  [
    "run",
    "--offline",
    "--frozen",
    "--directory",
    `${repositoryRoot}/apps/backend`,
    "python",
    "-m",
    "english_er.infra.build",
  ],
  { cwd: repositoryRoot, encoding: "utf8" },
).trim();

const backendUrl = process.env.VITE_SERVER_URL ?? "http://127.0.0.1:8001";

export default defineConfig({
  define: { __BUILD_INFO__: buildIdentity },
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "english-er-build-identity",
      generateBundle() {
        this.emitFile({ type: "asset", fileName: "version.json", source: `${buildIdentity}\n` });
      },
      configureServer(server) {
        server.middlewares.use("/version.json", (_request, response) => {
          response.setHeader("Content-Type", "application/json");
          response.setHeader("Cache-Control", "no-store");
          response.end(buildIdentity);
        });
      },
    },
  ],
  build: {
    outDir: "dist",
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": backendUrl,
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
