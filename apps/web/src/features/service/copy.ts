export const copy = {
  checking: "Checking service",
  ready: "Local service ready",
  unavailable: "API unavailable",
} as const;

export const aboutCopy = {
  title: "About English-er",
  purpose:
    "Practice English by reviewing corrections to your dictated text and listening to local speech playback.",
  version: "Version",
  revision: "Revision",
  commitTime: "Commit time",
  buildTime: "Build time",
  development: "Development build",
  check: "Check build",
  reload: "Reload",
  status: {
    idle: "",
    checking: "Checking the running build…",
    current: "You are viewing the running build.",
    changed: "A different build is running. Save any edits, then reload to use it.",
    failed: "Could not check the running build. Try again when the local service is available.",
  },
} as const;
