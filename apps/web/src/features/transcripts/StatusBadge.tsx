import { cx } from "../../shared/cx";
import type { TranscriptSummary } from "./api";
import { copy } from "./copy";

type Status = TranscriptSummary["status"];
const statusClasses: Record<Status, string> = {
  pending: "bg-honey-100 text-honey-800",
  processing: "bg-honey-100 text-honey-800",
  completed: "bg-sage-100 text-sage-700",
  failed: "bg-clay-100 text-clay-700",
};
export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={cx(
        "inline-flex w-fit items-center rounded-full px-2 py-0.5 text-2xs font-extrabold tracking-badge uppercase",
        statusClasses[status],
      )}
    >
      {copy.status[status]}
    </span>
  );
}
