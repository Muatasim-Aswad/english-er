import { useState } from "react";
import { Button } from "../../shared/ui/Button";
import { PanelTitle } from "../../shared/ui/typography";
import type { useTranscriptReview } from "./useTranscriptReview";
import { copy } from "./copy";

type Props = {
  review: ReturnType<typeof useTranscriptReview>;
  selectedIndex: number;
  count: number;
  navigateTranscript: (offset: -1 | 1) => void;
};
export function ReviewActions({ review, selectedIndex, count, navigateTranscript }: Props) {
  const {
    detail,
    busy: actionBusy,
    review: updateReview,
    retry: retrySelected,
    remove: permanentlyDelete,
  } = review;
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (detail === null) return null;
  return (
    <>
      <div
        aria-label={copy.actions}
        className="mt-7 flex flex-wrap items-center gap-4 border-t border-line-soft pt-5"
        role="group"
      >
        <Button
          disabled={actionBusy !== null || selectedIndex >= count - 1}
          onClick={() => navigateTranscript(1)}
        >
          {copy.next}
        </Button>
        <Button
          disabled={actionBusy !== null || selectedIndex <= 0}
          onClick={() => navigateTranscript(-1)}
        >
          {copy.previous}
        </Button>
        <Button
          disabled={actionBusy !== null || detail.status !== "completed"}
          onClick={() => void updateReview()}
        >
          {detail.reviewed_at === null ? copy.markReviewed : copy.markUnreviewed}
        </Button>
        {detail.status === "failed" && (
          <Button disabled={actionBusy !== null} onClick={() => void retrySelected()}>
            {copy.retry}
          </Button>
        )}
        <Button
          disabled={actionBusy !== null}
          onClick={() => setConfirmDelete(true)}
          variant="danger"
        >
          {copy.delete}
        </Button>
      </div>
      {confirmDelete && (
        <div
          className="mt-4 rounded-xl border border-clay-500 bg-clay-50 p-4"
          role="alertdialog"
          aria-labelledby="delete-title"
          aria-describedby="delete-description"
        >
          <PanelTitle className="mb-3" id="delete-title">
            {copy.deleteTitle}
          </PanelTitle>
          <p className="mb-4 leading-normal text-clay-900" id="delete-description">
            {copy.deleteBody}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Button
              autoFocus
              disabled={actionBusy !== null}
              onClick={() => void permanentlyDelete()}
              variant="danger"
            >
              {copy.confirmDelete}
            </Button>
            <Button disabled={actionBusy !== null} onClick={() => setConfirmDelete(false)}>
              {copy.cancel}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
