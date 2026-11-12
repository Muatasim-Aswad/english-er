import type { HTMLAttributes } from "react";

import { cx } from "../cx";

export function Eyebrow({ children }: { children: string }) {
  return (
    <p className="mb-1.5 text-xs font-extrabold tracking-eyebrow text-muted-strong uppercase">
      {children}
    </p>
  );
}

export function SectionTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cx("font-serif text-title font-medium", className)} {...props} />;
}

export function PanelTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cx("text-caption font-bold tracking-label uppercase", className)} {...props} />
  );
}

export function DisplayTitle({ children }: { children: string }) {
  return <h1 className="font-serif text-display font-medium">{children}</h1>;
}

export function InlineError({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cx("text-caption text-clay-700", className)} role="alert" {...props} />;
}
