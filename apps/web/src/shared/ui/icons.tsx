import type { ReactNode } from "react";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      className="size-4.25"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.8}
      viewBox="0 0 24 24"
    >
      {children}
    </svg>
  );
}

export function HistoryIcon() {
  return (
    <Icon>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
      <path d="M12 7v5l3 2" />
    </Icon>
  );
}

export function EditIcon() {
  return (
    <Icon>
      <path d="m4 20 4.2-1 10.6-10.6a2.1 2.1 0 0 0-3-3L5.2 16Z" />
      <path d="m14.5 6.5 3 3" />
    </Icon>
  );
}

export function SpeakerIcon() {
  return (
    <Icon>
      <path d="M11 5 6.5 9H3v6h3.5l4.5 4Z" />
      <path d="M15 9.5a4 4 0 0 1 0 5" />
      <path d="M17.5 7a7.5 7.5 0 0 1 0 10" />
    </Icon>
  );
}
