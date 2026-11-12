import { useCallback, useState } from "react";
import { Button } from "../../shared/ui/Button";
import { useVisiblePolling } from "../../shared/useVisiblePolling";
import { ReviewPanel } from "./ReviewPanel";
import { TranscriptList } from "./TranscriptList";
import { useTranscriptQueue } from "./useTranscriptQueue";
import { useTranscriptReview } from "./useTranscriptReview";
import { copy, viewLabels } from "./copy";
import type { View } from "./model";

export function ReviewWorkspace() {
  const [view, setView] = useState<View>("inbox");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queue = useTranscriptQueue(view, selectedId);
  const review = useTranscriptReview(selectedId, {
    onUpdate: queue.update,
    onDelete: (id) => {
      queue.remove(id);
      setSelectedId((selected) => (selected === id ? null : selected));
    },
    onReviewed: (id) => {
      if (view === "inbox") queue.remove(id);
    },
    onRetry: () => {
      if (view === "failed") void queue.load("refresh");
    },
  });
  const poll = useCallback(() => {
    void queue.load("poll");
    void review.load(true);
  }, [queue.load, review.load]);
  useVisiblePolling(poll);
  const chooseTranscript = (id: string) => {
    if (id !== selectedId) queue.leave(selectedId);
    setSelectedId(id);
  };
  const selectedIndex = queue.items.findIndex((item) => item.id === selectedId);
  const navigateTranscript = (offset: -1 | 1) => {
    const target = queue.items[selectedIndex + offset];
    if (target !== undefined) chooseTranscript(target.id);
  };
  return (
    <>
      <nav className="flex gap-2 overflow-x-auto py-5" aria-label={copy.views}>
        {(Object.keys(viewLabels) as View[]).map((candidate) => (
          <Button
            aria-pressed={view === candidate}
            key={candidate}
            onClick={() => {
              setSelectedId(null);
              setView(candidate);
            }}
            variant="tab"
          >
            {viewLabels[candidate]}
          </Button>
        ))}
      </nav>
      <div className="grid min-h-160 grid-cols-1 overflow-hidden rounded-2xl border border-line bg-surface/72 shadow-workspace md:grid-cols-workspace">
        <TranscriptList
          queue={queue}
          view={view}
          selectedId={selectedId}
          chooseTranscript={chooseTranscript}
        />
        <ReviewPanel
          review={review}
          selectedId={selectedId}
          selectedIndex={selectedIndex}
          count={queue.items.length}
          navigateTranscript={navigateTranscript}
        />
      </div>
    </>
  );
}
