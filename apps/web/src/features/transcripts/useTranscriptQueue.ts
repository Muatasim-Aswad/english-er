import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../infra/http";
import { messageFrom } from "../../shared/errors";
import { listTranscripts, type TranscriptSummary } from "./api";
import { copy } from "./copy";
import { sameSummaries, viewQuery, type ListLoadMode, type LoadState, type View } from "./model";

export function useTranscriptQueue(view: View, selectedId: string | null) {
  const [items, setItems] = useState<TranscriptSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const sequence = useRef(0);
  const visibleLoading = useRef(false);
  const cursor = useRef<string | null>(null);
  const selected = useRef(selectedId);
  selected.current = selectedId;

  const load = useCallback(
    async (mode: ListLoadMode = "initial") => {
      if (mode === "poll" && visibleLoading.current) return;
      const request = ++sequence.current;
      const visible = mode === "refresh" || mode === "more";
      if (mode === "initial") {
        visibleLoading.current = false;
        setRefreshing(false);
        setState("loading");
        setItems([]);
        setNextCursor(null);
        cursor.current = null;
      }
      if (visible) {
        visibleLoading.current = true;
        setRefreshing(true);
      }
      if (mode !== "poll") setNotice(null);
      try {
        const page = await listTranscripts({
          ...viewQuery(view),
          ...(mode === "more" && cursor.current !== null ? { cursor: cursor.current } : {}),
        });
        if (request !== sequence.current) return;
        setItems((current) => {
          let next = mode === "more" ? [...current, ...page.items] : page.items;
          const active = current.find((item) => item.id === selected.current);
          if (
            mode === "poll" &&
            view === "inbox" &&
            active !== undefined &&
            (active.status !== "completed" || active.reviewed_at !== null) &&
            !next.some((item) => item.id === active.id)
          ) {
            next = [...next];
            next.splice(Math.min(current.indexOf(active), next.length), 0, active);
          }
          return sameSummaries(current, next) ? current : next;
        });
        setNextCursor(page.metadata.next_cursor);
        cursor.current = page.metadata.next_cursor;
        setState(page.items.length === 0 && mode !== "more" ? "empty" : "ready");
      } catch (error) {
        if (request !== sequence.current) return;
        if (mode === "initial")
          setState(
            error instanceof TypeError || (error instanceof ApiError && error.status === 503)
              ? "unavailable"
              : "error",
          );
        else if (mode !== "poll") setNotice(copy.refreshFailed(messageFrom(error)));
      } finally {
        if (request === sequence.current && visible) {
          visibleLoading.current = false;
          setRefreshing(false);
        }
      }
    },
    [view],
  );

  useEffect(() => {
    void load();
    return () => {
      sequence.current += 1;
    };
  }, [load]);

  const update = useCallback((item: TranscriptSummary) => {
    setItems((current) => current.map((existing) => (existing.id === item.id ? item : existing)));
  }, []);
  const remove = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);
  const leave = (id: string | null) => {
    if (view === "inbox" && id !== null)
      setItems((current) => current.filter((item) => item.id !== id || item.reviewed_at === null));
  };
  const displayState =
    state === "ready" || state === "empty" ? (items.length > 0 ? "ready" : "empty") : state;
  return {
    items,
    nextCursor,
    state: displayState,
    refreshing,
    notice,
    load,
    update,
    remove,
    leave,
  };
}
