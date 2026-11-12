import { sharedCopy } from "./copy";

export function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : sharedCopy.unexpected;
}
