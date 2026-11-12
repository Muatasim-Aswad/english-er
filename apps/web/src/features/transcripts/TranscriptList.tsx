import { Button } from "../../shared/ui/Button";
import { ListMessage } from "../../shared/ui/ListMessage";
import { Eyebrow, SectionTitle } from "../../shared/ui/typography";
import { dateLabel } from "../../infra/format";
import { StatusBadge } from "./StatusBadge";
import { copy, viewLabels } from "./copy";
import type { View } from "./model";
import type { useTranscriptQueue } from "./useTranscriptQueue";

type Props = {
  queue: ReturnType<typeof useTranscriptQueue>;
  view: View;
  selectedId: string | null;
  chooseTranscript: (id: string) => void;
};
export function TranscriptList({ queue, view, selectedId, chooseTranscript }: Props) {
  const {
    items,
    nextCursor,
    state: listState,
    refreshing,
    notice: listNotice,
    load: loadList,
  } = queue;
  return (
    <section
      className="border-b border-line p-column md:border-r md:border-b-0"
      aria-labelledby="list-heading"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <Eyebrow>{copy.queue}</Eyebrow>
          <SectionTitle id="list-heading">{viewLabels[view]}</SectionTitle>
        </div>
        <Button
          disabled={refreshing}
          onClick={() => void loadList("refresh")}
          size="sm"
          variant="quiet"
        >
          {refreshing ? copy.refreshing : copy.refresh}
        </Button>
      </div>
      <div className="min-h-6 py-2 text-xs text-clay-700" aria-live="polite">
        {refreshing && copy.refreshingList}
        {listNotice}
      </div>

      {listState === "loading" && <ListMessage title={copy.loadingTitle} body={copy.loadingBody} />}
      {listState === "empty" && (
        <ListMessage
          title={copy.emptyTitle}
          body={view === "inbox" ? copy.emptyInbox : copy.emptyOther}
        />
      )}
      {listState === "unavailable" && (
        <ListMessage
          title={copy.unavailableTitle}
          body={copy.unavailableBody}
          action={() => void loadList("initial")}
        />
      )}
      {listState === "error" && (
        <ListMessage
          title={copy.listErrorTitle}
          body={copy.listErrorBody}
          action={() => void loadList("initial")}
        />
      )}

      {items.length > 0 && (
        <ul className="grid gap-2.5" aria-label={copy.listLabel(view)}>
          {items.map((item) => (
            <li key={item.id}>
              <button
                aria-current={selectedId === item.id ? "true" : undefined}
                className="grid w-full gap-3 rounded-xl border border-transparent p-4 text-left text-ink-soft hover:bg-white/58 aria-[current=true]:border-control aria-[current=true]:bg-card aria-[current=true]:shadow-card"
                onClick={() => chooseTranscript(item.id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-4">
                  <StatusBadge status={item.status} />
                  <time className="text-xs text-muted" dateTime={item.captured_at}>
                    {dateLabel(item.captured_at)}
                  </time>
                </span>
                <strong className="line-clamp-2 font-serif text-lg leading-snug font-medium text-ink">
                  {item.preview}
                </strong>
                <span className="text-xs text-muted">
                  {copy.listMeta(item.reviewed_at !== null, item.attempt_count)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {nextCursor !== null && (
        <Button
          className="mt-4 w-full"
          disabled={refreshing}
          onClick={() => void loadList("more")}
          variant="quiet"
        >
          {refreshing ? copy.loadingMore : copy.loadMore}
        </Button>
      )}
    </section>
  );
}
