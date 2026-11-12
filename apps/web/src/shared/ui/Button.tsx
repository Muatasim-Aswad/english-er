import type { ButtonHTMLAttributes } from "react";

import { cx } from "../cx";

type ButtonVariant = "default" | "quiet" | "danger" | "tab" | "chip";
type ButtonSize = "md" | "sm" | "xs";

const variantClasses: Record<ButtonVariant, string> = {
  default: "border-control bg-surface",
  quiet: "border-control bg-transparent",
  danger: "border-clay-500 bg-clay-50 text-clay-700",
  tab: "border-control bg-surface aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-white",
  chip: "border-control bg-surface hover:border-sage-400 hover:bg-sage-100 hover:text-sage-700 aria-pressed:border-sage-400 aria-pressed:bg-sage-100 aria-pressed:text-sage-700",
};

const sizeClasses: Record<ButtonSize, string> = {
  md: "px-4 py-2.5",
  sm: "px-3.5 py-2 text-caption",
  xs: "px-2 py-1 text-xs",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export function Button({
  variant = "default",
  size = "md",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx(
        "rounded-full border font-bold",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      type={type}
      {...props}
    />
  );
}
