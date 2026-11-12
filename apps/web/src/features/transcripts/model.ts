import type { TranscriptSummary } from "./api";

export type View = "inbox" | "all" | "failed";
export type LoadState = "loading" | "ready" | "empty" | "error" | "unavailable";
export type DetailState = "idle" | "loading" | "ready" | "error" | "unavailable" | "stale";
export type ListLoadMode = "initial" | "refresh" | "more" | "poll";

export function viewQuery(view: View) {
  if (view === "inbox") {
    return { status: "completed" as const, reviewed: "unreviewed" as const };
  }
  if (view === "failed") {
    return { status: "failed" as const };
  }
  return {};
}

export function sameSummaries(left: TranscriptSummary[], right: TranscriptSummary[]): boolean {
  return (
    left.length === right.length &&
    left.every((item, index) => {
      const candidate = right[index];
      return (
        candidate !== undefined &&
        item.id === candidate.id &&
        item.source === candidate.source &&
        item.preview === candidate.preview &&
        item.captured_at === candidate.captured_at &&
        item.reviewed_at === candidate.reviewed_at &&
        item.status === candidate.status &&
        item.attempt_count === candidate.attempt_count &&
        item.last_error === candidate.last_error
      );
    })
  );
}
