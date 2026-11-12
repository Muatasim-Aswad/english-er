import { apiClient, unwrap } from "../../infra/http";
import type { paths } from "../../infra/schema";
type HealthResponse =
  paths["/api/v1/health"]["get"]["responses"][200]["content"]["application/json"];

export async function getHealth(): Promise<HealthResponse> {
  return unwrap<HealthResponse>(await apiClient.GET("/api/v1/health"));
}
