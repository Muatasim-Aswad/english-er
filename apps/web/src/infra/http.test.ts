import { describe, expect, it } from "vitest";
import { normalizeApiError } from "./http";

describe("HTTP error contract", () => {
  it("preserves stable codes, correlation IDs, and safe conflict details", () => {
    const error = normalizeApiError(409, {
      error: {
        status: 409,
        code: "revision_conflict",
        message: "The transcript changed.",
        request_id: "request-1",
        details: { current_revision: 2 },
      },
    });
    expect(error.code).toBe("revision_conflict");
    expect(error.requestId).toBe("request-1");
    expect(error.details).toEqual({ current_revision: 2 });
    expect(error.status).toBe(409);
  });
  it("uses a safe fallback for non-contract responses", () => {
    const error = normalizeApiError(500, "private upstream diagnostics");
    expect(error.code).toBe("unknown");
    expect(error.message).not.toContain("private upstream diagnostics");
  });
});
