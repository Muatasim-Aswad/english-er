import { useEffect, useRef, useState } from "react";
import { buildInfo } from "../../config";
import { getServedBuild } from "../../infra/build";
import { Button } from "../../shared/ui/Button";
import { aboutCopy as copy } from "./copy";

const noticeKey = "english-er.update-revision.v1";

function shouldNotify(revision: string): boolean {
  try {
    if (localStorage.getItem(noticeKey) === revision) return false;
    localStorage.setItem(noticeKey, revision);
  } catch {
    // Build checks remain usable when browser storage is unavailable.
  }
  return true;
}

export function About() {
  const [status, setStatus] = useState<"idle" | "checking" | "current" | "changed" | "failed">(
    "idle",
  );
  const [notify, setNotify] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function check() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setStatus("checking");
    setNotify(false);
    try {
      const served = await getServedBuild(controller.signal);
      if (controller.signal.aborted) return;
      const changed =
        served.version !== buildInfo.version ||
        served.revision !== buildInfo.revision ||
        served.build_time !== buildInfo.build_time;
      setStatus(changed ? "changed" : "current");
      if (changed) setNotify(shouldNotify(served.revision));
    } catch {
      if (!controller.signal.aborted) setStatus("failed");
    }
  }

  return (
    <details
      className="mt-9 max-w-2xl border-t border-line pt-4 text-sm text-ink-soft"
      onToggle={(event) => {
        if (event.currentTarget.open) void check();
      }}
    >
      <summary className="w-fit cursor-pointer rounded-sm font-bold focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-accent">
        {copy.title}
      </summary>
      <p className="mt-4 max-w-prose leading-relaxed">{copy.purpose}</p>
      <dl className="my-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-2">
        <dt>{copy.version}</dt>
        <dd>{buildInfo.version}</dd>
        <dt>{copy.revision}</dt>
        <dd className="break-all">{buildInfo.revision}</dd>
        <dt>{copy.commitTime}</dt>
        <dd>{buildInfo.commit_time ?? copy.development}</dd>
        <dt>{copy.buildTime}</dt>
        <dd>{buildInfo.build_time}</dd>
      </dl>
      <p role={notify ? "alert" : "status"}>{copy.status[status]}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="quiet"
          disabled={status === "checking"}
          onClick={() => void check()}
        >
          {copy.check}
        </Button>
        {status === "changed" ? (
          <Button size="sm" onClick={() => window.location.reload()}>
            {copy.reload}
          </Button>
        ) : null}
      </div>
    </details>
  );
}
