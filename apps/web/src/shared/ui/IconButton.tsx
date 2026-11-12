import type { ButtonHTMLAttributes } from "react";

import { cx } from "../cx";

type IconButtonTone = "neutral" | "processing" | "existing";

const toneClasses: Record<IconButtonTone, string> = {
  neutral:
    "border-transparent bg-transparent hover:border-line hover:bg-mist aria-pressed:border-line aria-pressed:bg-mist",
  processing: "border-honey-400 bg-honey-50 text-honey-700 disabled:opacity-100",
  existing: "border-sage-400 bg-sage-100 text-sage-700",
};

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  tone?: IconButtonTone;
};

export function IconButton({
  label,
  tone = "neutral",
  type = "button",
  ...props
}: IconButtonProps) {
  return (
    <button
      aria-label={label}
      className={cx("inline-grid size-8 place-items-center rounded-full border", toneClasses[tone])}
      data-tone={tone}
      title={label}
      type={type}
      {...props}
    />
  );
}
