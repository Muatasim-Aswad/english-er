import { errorMessages } from "./copy";
import type { paths } from "../../infra/schema";
import {
  apiClient,
  ApiError,
  normalizeApiError,
  unwrap as unwrapResponse,
  unwrapEmpty as unwrapEmptyResponse,
} from "../../infra/http";

function localize(error: unknown): never {
  if (error instanceof ApiError) {
    throw new ApiError(
      error.status,
      errorMessages[error.code] ?? error.message,
      error.code,
      error.details,
      error.requestId,
    );
  }
  throw error;
}
const unwrap: typeof unwrapResponse = (result) => {
  try {
    return unwrapResponse(result);
  } catch (error) {
    return localize(error);
  }
};
const unwrapEmpty: typeof unwrapEmptyResponse = (result) => {
  try {
    return unwrapEmptyResponse(result);
  } catch (error) {
    localize(error);
  }
};

export type TranscriptPage =
  paths["/api/v1/transcripts"]["get"]["responses"][200]["content"]["application/json"];
export type TranscriptSummary = TranscriptPage["items"][number];
export type TranscriptDetail =
  paths["/api/v1/transcripts/{id}"]["get"]["responses"][200]["content"]["application/json"];
export type ProcessingStatus = NonNullable<
  NonNullable<paths["/api/v1/transcripts"]["get"]["parameters"]["query"]>["status"]
>;
export type ReviewedState = NonNullable<
  NonNullable<paths["/api/v1/transcripts"]["get"]["parameters"]["query"]>["reviewed"]
>;

export async function listTranscripts(options: {
  cursor?: string;
  status?: ProcessingStatus;
  reviewed?: ReviewedState;
}): Promise<TranscriptPage> {
  return unwrap<TranscriptPage>(
    await apiClient.GET("/api/v1/transcripts", {
      params: { query: { ...options, limit: 20 } },
    }),
  );
}

export async function getTranscript(id: string): Promise<TranscriptDetail> {
  return unwrap<TranscriptDetail>(
    await apiClient.GET("/api/v1/transcripts/{id}", { params: { path: { id } } }),
  );
}

export async function getTranscriptAudio(id: string, expectedRevision: number): Promise<Blob> {
  const result = await apiClient.POST("/api/v1/transcripts/{id}/audio", {
    params: { path: { id } },
    body: { expected_revision: expectedRevision },
    parseAs: "blob",
  });
  if (result.response.ok && result.data instanceof Blob) {
    return result.data;
  }
  localize(normalizeApiError(result.response.status, result.error));
}

export async function setTranscriptReview(
  id: string,
  reviewed: boolean,
): Promise<TranscriptDetail> {
  return unwrap<TranscriptDetail>(
    await apiClient.PUT("/api/v1/transcripts/{id}/review", {
      params: { path: { id } },
      body: { reviewed },
    }),
  );
}

export async function updateTranscriptText(
  id: string,
  text: string,
  expectedRevision: number,
): Promise<TranscriptDetail> {
  return unwrap<TranscriptDetail>(
    await apiClient.PUT("/api/v1/transcripts/{id}/text", {
      params: { path: { id } },
      body: { text, expected_revision: expectedRevision },
    }),
  );
}

export async function retryTranscript(id: string): Promise<TranscriptSummary> {
  return unwrap<TranscriptSummary>(
    await apiClient.POST("/api/v1/transcripts/{id}/retry", { params: { path: { id } } }),
  );
}

export async function deleteTranscript(id: string): Promise<void> {
  unwrapEmpty(await apiClient.DELETE("/api/v1/transcripts/{id}", { params: { path: { id } } }));
}
