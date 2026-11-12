import { useEffect, useState } from "react";
import { ApiError } from "../../infra/http";
import { messageFrom } from "../../shared/errors";
import { InlineError } from "../../shared/ui/typography";
import { getCapture, setCapture } from "./api";
import { copy } from "./copy";

export function CaptureSwitch() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void getCapture()
      .then((state) => {
        if (active) setEnabled(state.enabled);
      })
      .catch((error: unknown) => {
        if (active) setNotice(messageFrom(error));
      });
    return () => {
      active = false;
    };
  }, []);
  const toggle = async () => {
    if (enabled === null || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      setEnabled((await setCapture(!enabled)).enabled);
    } catch (error) {
      const message =
        error instanceof ApiError && error.code === "capture_unavailable"
          ? copy.unavailable
          : messageFrom(error);
      setNotice(copy.changeFailed(message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button
        aria-checked={enabled ?? false}
        className="group inline-flex min-w-38 items-center gap-2.5 rounded-full border border-control bg-surface px-3.5 py-2 font-bold"
        disabled={enabled === null || busy}
        onClick={() => void toggle()}
        role="switch"
        type="button"
      >
        <span
          className="w-8 rounded-full bg-control p-0.5 group-aria-checked:bg-accent"
          aria-hidden="true"
        >
          <span className="block size-3 rounded-full bg-white group-aria-checked:translate-x-4 motion-safe:transition-transform" />
        </span>
        <span>{enabled === null ? copy.loading : enabled ? copy.enabled : copy.disabled}</span>
      </button>
      {notice !== null && <InlineError>{notice}</InlineError>}
    </>
  );
}
