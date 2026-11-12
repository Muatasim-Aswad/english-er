import type { HTMLAttributes } from "react";

import { cx } from "../cx";

type PanelTone = "neutral" | "corrected";

const toneClasses: Record<PanelTone, string> = {
  neutral: "bg-panel",
  corrected: "border-l-4 border-sage-500 bg-sage-50",
};

type PanelProps = HTMLAttributes<HTMLElement> & { tone?: PanelTone };

export function Panel({ tone = "neutral", className, ...props }: PanelProps) {
  return (
    <section className={cx("mt-5 rounded-xl p-4.5", toneClasses[tone], className)} {...props} />
  );
}

export function PanelText(props: HTMLAttributes<HTMLParagraphElement>) {
  return <p className="leading-relaxed whitespace-pre-wrap" {...props} />;
}
