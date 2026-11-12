import { ListMessage } from "../../shared/ui/ListMessage";
import { Eyebrow, InlineError, SectionTitle } from "../../shared/ui/typography";
import { dateLabel } from "../../infra/format";
import { CorrectionPanel } from "./CorrectionPanel";
import { TranscriptEditor } from "./TranscriptEditor";
import { ReviewActions } from "./ReviewActions";
import { StatusBadge } from "./StatusBadge";
import { copy } from "./copy";
import type { useTranscriptReview } from "./useTranscriptReview";

type Props = {
  review: ReturnType<typeof useTranscriptReview>;
  selectedId: string | null;
  selectedIndex: number;
  count: number;
  navigateTranscript: (offset: -1 | 1) => void;
};
export function ReviewPanel({
  review,
  selectedId,
  selectedIndex,
  count,
  navigateTranscript,
}: Props) {
  const { detail, state: detailState, notice: detailNotice } = review;
  return (
    <section className="min-h-112 bg-white/32 p-column md:min-h-0" aria-labelledby="review-heading">
      {detailState === "idle" && (
        <div className="mx-auto grid min-h-72 max-w-120 content-center justify-items-start">
          <Eyebrow>{copy.panel}</Eyebrow>
          <SectionTitle id="review-heading">{copy.chooseTitle}</SectionTitle>
          <p className="mt-3 leading-relaxed text-muted">{copy.chooseBody}</p>
        </div>
      )}
      {detailState === "loading" && (
        <ListMessage title={copy.loadingReview} body={copy.loadingReviewBody} />
      )}
      {(detailState === "unavailable" || detailState === "error" || detailState === "stale") && (
        <ListMessage
          title={
            detailState === "stale"
              ? copy.staleTitle
              : detailState === "unavailable"
                ? copy.unavailableTitle
                : copy.reviewError
          }
          body={detailNotice ?? copy.selectAgain}
          action={selectedId === null ? undefined : () => void review.load()}
        />
      )}
      {detailState === "ready" && detail !== null && (
        <article>
          <div className="flex items-start justify-between gap-4">
            <div>
              <Eyebrow>{copy.panel}</Eyebrow>
              <SectionTitle id="review-heading">{copy.reviewTitle}</SectionTitle>
              <p className="mt-3 mb-3 flex items-center gap-2.5 text-xs text-muted">
                <StatusBadge status={detail.status} />{" "}
                {copy.capturedAt(dateLabel(detail.captured_at))}
              </p>
            </div>
            <span className="rounded-full border border-line px-2.5 py-1.5 text-xs font-bold text-muted uppercase">
              {detail.source}
            </span>
          </div>
          {detailNotice !== null && <InlineError>{detailNotice}</InlineError>}
          <TranscriptEditor
            key={`editor:${detail.id}`}
            detail={detail}
            busy={review.busy !== null}
            onSave={review.save}
          />
          <CorrectionPanel
            key={`correction:${detail.id}`}
            detail={detail}
            onStale={() => void review.load(true)}
          />
          <ReviewActions
            key={`actions:${detail.id}`}
            review={review}
            selectedIndex={selectedIndex}
            count={count}
            navigateTranscript={navigateTranscript}
          />
        </article>
      )}
    </section>
  );
}
