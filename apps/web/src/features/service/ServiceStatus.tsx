import { useCallback, useEffect, useRef, useState } from "react";
import { cx } from "../../shared/cx";
import { useVisiblePolling } from "../../shared/useVisiblePolling";
import { getHealth } from "./api";
import { copy } from "./copy";

export function ServiceStatus() {
  const [online, setOnline] = useState<boolean | null>(null);
  const active = useRef(false);
  const load = useCallback(() => {
    void getHealth()
      .then((health) => {
        if (active.current) setOnline(health.api === "ok" && health.database === "ok");
      })
      .catch(() => {
        if (active.current) setOnline(false);
      });
  }, []);
  useEffect(() => {
    active.current = true;
    load();
    return () => {
      active.current = false;
    };
  }, [load]);
  useVisiblePolling(load);
  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 text-xs font-bold",
        online === false ? "text-clay-700" : "text-ink-soft",
      )}
      role="status"
    >
      <span
        aria-hidden="true"
        className={cx(
          "size-2 rounded-full ring-4",
          online === false ? "bg-clay-500 ring-clay-500/12" : "bg-sage-500 ring-sage-500/12",
        )}
      />
      {online === null ? copy.checking : online ? copy.ready : copy.unavailable}
    </span>
  );
}
