import { sharedCopy } from "../copy";
import { Button } from "./Button";
import { SectionTitle } from "./typography";

type ListMessageProps = {
  title: string;
  body: string;
  action?: (() => void) | undefined;
};

export function ListMessage({ title, body, action }: ListMessageProps) {
  return (
    <div
      className="mx-auto grid min-h-72 max-w-120 content-center justify-items-start"
      role="status"
    >
      <SectionTitle>{title}</SectionTitle>
      <p className="mt-3 mb-4 leading-relaxed text-muted">{body}</p>
      {action !== undefined && <Button onClick={action}>{sharedCopy.retry}</Button>}
    </div>
  );
}
