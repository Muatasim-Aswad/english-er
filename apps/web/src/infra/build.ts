import type { BuildInfo } from "../shared/build";

export async function getServedBuild(signal: AbortSignal): Promise<BuildInfo> {
  const response = await fetch("/version.json", {
    cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(5_000)]),
  });
  if (!response.ok) throw new Error("Build check failed");
  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("version" in body) ||
    typeof body.version !== "string" ||
    !("revision" in body) ||
    typeof body.revision !== "string" ||
    !("build_time" in body) ||
    typeof body.build_time !== "string" ||
    !("commit_time" in body) ||
    !(body.commit_time === null || typeof body.commit_time === "string")
  )
    throw new Error("Invalid build identity");
  return {
    version: body.version,
    revision: body.revision,
    build_time: body.build_time,
    commit_time: body.commit_time,
  };
}
