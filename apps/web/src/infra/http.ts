import createClient from "openapi-fetch";
import { sharedCopy } from "../shared/copy";
import type { paths } from "./schema";

const baseUrl = typeof window === "undefined" ? "http://localhost" : window.location.origin;
const sameOriginFetch: typeof fetch = (input, init) => globalThis.fetch(input, init);
export const apiClient = createClient<paths>({ baseUrl, fetch: sameOriginFetch });

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string,
    readonly details?: Record<string, unknown>,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function normalizeApiError(status: number, payload: unknown): ApiError {
  const outer =
    typeof payload === "object" && payload !== null && "error" in payload
      ? payload.error
      : undefined;
  const body =
    typeof outer === "object" && outer !== null ? (outer as Record<string, unknown>) : {};
  return new ApiError(
    status,
    typeof body.message === "string" ? body.message : sharedCopy.unavailable,
    typeof body.code === "string" ? body.code : "unknown",
    typeof body.details === "object" && body.details !== null
      ? (body.details as Record<string, unknown>)
      : undefined,
    typeof body.request_id === "string" ? body.request_id : undefined,
  );
}

type ApiResult<T> = {
  data?: T | undefined;
  error?: unknown;
  response: Response;
};

export function unwrap<T>({ data, error, response }: ApiResult<T>): T {
  if (response.ok && data !== undefined) {
    return data;
  }
  throw normalizeApiError(response.status, error);
}

export function unwrapEmpty({ error, response }: ApiResult<never>): void {
  if (response.ok) {
    return;
  }
  throw normalizeApiError(response.status, error);
}
