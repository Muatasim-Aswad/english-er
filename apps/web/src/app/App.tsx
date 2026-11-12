import { CaptureSwitch } from "../features/capture";
import { About, ServiceStatus } from "../features/service";
import { ReviewWorkspace } from "../features/transcripts";
import { DisplayTitle, Eyebrow } from "../shared/ui/typography";
import { copy } from "./copy";

export function App() {
  return (
    <main className="mx-auto box-content max-w-shell px-2.5 pt-5 pb-16 sm:px-5 sm:pt-9">
      <header className="flex flex-col items-start justify-between gap-4 border-b border-line pb-7 sm:flex-row sm:items-end">
        <div>
          <Eyebrow>{copy.eyebrow}</Eyebrow>
          <DisplayTitle>{copy.title}</DisplayTitle>
        </div>
        <div className="grid w-full justify-items-start gap-2.5 sm:w-auto sm:justify-items-end">
          <ServiceStatus />
          <CaptureSwitch />
        </div>
      </header>
      <ReviewWorkspace />
      <About />
    </main>
  );
}
