import { useEffect } from "react";

export function useVisiblePolling(refresh: () => void, interval = 5_000) {
  useEffect(() => {
    let timer: number | undefined;
    const stop = () => {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    };
    const start = () => {
      stop();
      if (document.visibilityState === "visible") timer = window.setInterval(refresh, interval);
    };
    const onVisibilityChange = () => {
      start();
      if (document.visibilityState === "visible") refresh();
    };
    start();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [refresh, interval]);
}
