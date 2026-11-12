import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../infra/http";
import { messageFrom } from "../../shared/errors";
import { getTranscriptAudio, type TranscriptDetail } from "./api";

type AudioState = "idle" | "loading" | "ready" | "error";
export type PlaybackRate = 0.5 | 0.75 | 1;
export const playbackRates: PlaybackRate[] = [0.5, 0.75, 1];

export function useTranscriptAudio(detail: TranscriptDetail, onStale: () => void) {
  const [state, setState] = useState<AudioState>("idle");
  const [url, setUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rate, setRate] = useState<PlaybackRate>(1);
  const player = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const sequence = useRef(0);
  const stale = useRef(onStale);
  stale.current = onStale;
  const revision = detail.correction?.input_revision;
  const created = detail.correction?.created_at;
  const id = detail.id;

  const clear = useCallback(() => {
    sequence.current += 1;
    if (objectUrl.current !== null) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
    setUrl(null);
    setState("idle");
    setNotice(null);
  }, []);
  const prepare = useCallback(async () => {
    if (revision === undefined) return;
    clear();
    const request = ++sequence.current;
    setState("loading");
    try {
      const blob = await getTranscriptAudio(id, revision);
      if (request !== sequence.current) return;
      objectUrl.current = URL.createObjectURL(blob);
      setUrl(objectUrl.current);
      setState("ready");
    } catch (error) {
      if (request !== sequence.current) return;
      setState("error");
      setNotice(messageFrom(error));
      if (error instanceof ApiError && error.status === 409) stale.current();
    }
  }, [clear, id, revision]);
  useEffect(() => {
    void prepare();
    return clear;
  }, [prepare, clear, created]);
  useEffect(() => {
    if (player.current !== null) player.current.playbackRate = rate;
  }, [rate, url]);
  return {
    state,
    url,
    notice,
    rate,
    setRate,
    player,
    prepare,
    exists: detail.correction?.audio_available === true || state === "ready",
  };
}
