export const copy = {
  loading: "Loading capture",
  enabled: "Capture on",
  disabled: "Capture off",
  changeFailed: (message: string) => `Capture change failed: ${message}`,
  unavailable: "Capture state is unavailable.",
} as const;
