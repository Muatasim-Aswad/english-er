import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../infra/http";
import { messageFrom } from "../../shared/errors";
import {
  deleteTranscript,
  getTranscript,
  retryTranscript,
  setTranscriptReview,
  updateTranscriptText,
  type TranscriptDetail,
  type TranscriptSummary,
} from "./api";
import { copy } from "./copy";
import type { DetailState } from "./model";

function summaryOf(detail: TranscriptDetail): TranscriptSummary {
  const { id, source, captured_at, reviewed_at, status, attempt_count, last_error } = detail;
  return {
    id,
    source,
    captured_at,
    reviewed_at,
    status,
    attempt_count,
    last_error,
    preview: detail.preview,
  };
}

type Callbacks = {
  onUpdate: (summary: TranscriptSummary) => void;
  onDelete: (id: string) => void;
  onReviewed: (id: string) => void;
  onRetry: () => void;
};

export function useTranscriptReview(id: string | null, callbacks: Callbacks) {
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [state, setState] = useState<DetailState>("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const sequence = useRef(0);
  const mutation = useRef<{ id: string; token: symbol } | null>(null);
  const currentId = useRef(id);
  currentId.current = id;
  const handlers = useRef(callbacks);
  handlers.current = callbacks;

  const load = useCallback(
    async (background = false) => {
      if (id === null || (background && mutation.current?.id === id)) return;
      const request = ++sequence.current;
      if (!background) {
        setState("loading");
        setDetail(null);
        setNotice(null);
      }
      try {
        let next = await getTranscript(id);
        if (request !== sequence.current || id !== currentId.current) return;
        if (!background && next.status === "completed" && next.reviewed_at === null) {
          try {
            next = await setTranscriptReview(id, true);
            if (request !== sequence.current || id !== currentId.current) return;
            handlers.current.onUpdate(summaryOf(next));
          } catch (error) {
            if (request !== sequence.current) return;
            setNotice(copy.autoReviewFailed(messageFrom(error)));
          }
        }
        if (request !== sequence.current || id !== currentId.current) return;
        setDetail((current) =>
          current?.id === next.id && current.updated_at === next.updated_at ? current : next,
        );
        setState("ready");
      } catch (error) {
        if (request !== sequence.current || id !== currentId.current) return;
        if (error instanceof ApiError && error.status === 404) {
          setDetail(null);
          setState("stale");
          setNotice(copy.staleBody);
        } else if (!background) {
          setState(
            error instanceof TypeError || (error instanceof ApiError && error.status === 503)
              ? "unavailable"
              : "error",
          );
          setNotice(messageFrom(error));
        } else setNotice(copy.detailRefreshFailed(messageFrom(error)));
      }
    },
    [id],
  );

  useEffect(() => {
    setDetail(null);
    setNotice(null);
    setBusy(null);
    setState(id === null ? "idle" : "loading");
    void load();
    return () => {
      sequence.current += 1;
    };
  }, [id, load]);

  const mutate = async (
    action: string,
    operation: () => Promise<void>,
    failure: (message: string) => string,
  ) => {
    if (id === null || mutation.current?.id === id) return false;
    const token = Symbol();
    mutation.current = { id, token };
    const request = ++sequence.current;
    setBusy(action);
    setNotice(null);
    try {
      await operation();
      return true;
    } catch (error) {
      if (id !== currentId.current) return false;
      setNotice(failure(messageFrom(error)));
      if (error instanceof ApiError && error.status === 409) {
        if (mutation.current?.token === token) mutation.current = null;
        await load(true);
      }
      return false;
    } finally {
      if (mutation.current?.token === token) mutation.current = null;
      if (id === currentId.current) setBusy(null);
      if (request === sequence.current) sequence.current += 1;
    }
  };
  const accept = (updated: TranscriptDetail) => {
    if (id !== currentId.current) return;
    setDetail(updated);
    handlers.current.onUpdate(summaryOf(updated));
  };
  const save = async (text: string) => {
    if (detail === null) return;
    return await mutate(
      "transcript",
      async () => {
        accept(await updateTranscriptText(detail.id, text, detail.text_revision));
      },
      copy.saveFailed,
    );
  };
  const review = async () => {
    if (detail === null) return;
    const reviewed = detail.reviewed_at === null;
    await mutate(
      "review",
      async () => {
        const updated = await setTranscriptReview(detail.id, reviewed);
        accept(updated);
        if (id === currentId.current && reviewed) handlers.current.onReviewed(detail.id);
      },
      copy.reviewFailed,
    );
  };
  const retry = async () => {
    if (detail === null || detail.status !== "failed") return;
    await mutate(
      "retry",
      async () => {
        const updated = await retryTranscript(detail.id);
        if (id !== currentId.current) return;
        accept({ ...detail, ...updated, correction: null });
        handlers.current.onRetry();
      },
      copy.retryFailed,
    );
  };
  const remove = async () => {
    if (detail === null) return;
    await mutate(
      "delete",
      async () => {
        await deleteTranscript(detail.id);
        handlers.current.onDelete(detail.id);
      },
      copy.deleteFailed,
    );
  };
  return { detail, state, notice, busy, load, save, review, retry, remove };
}
