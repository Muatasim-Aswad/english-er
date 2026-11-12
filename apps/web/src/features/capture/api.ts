import { apiClient, unwrap } from "../../infra/http";
import type { paths } from "../../infra/schema";
type CaptureState =
  paths["/api/v1/capture"]["get"]["responses"][200]["content"]["application/json"];

export async function getCapture(): Promise<CaptureState> {
  return unwrap<CaptureState>(await apiClient.GET("/api/v1/capture"));
}

export async function setCapture(enabled: boolean): Promise<CaptureState> {
  return unwrap<CaptureState>(await apiClient.PUT("/api/v1/capture", { body: { enabled } }));
}
