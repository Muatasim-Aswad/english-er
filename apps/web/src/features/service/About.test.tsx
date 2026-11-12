import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { buildInfo } from "../../config";
import { About } from "./About";

function openAbout() {
  const details = screen.getByText("About English-er").closest("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it("checks only on request and recognizes the running build", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(buildInfo)));
  vi.stubGlobal("fetch", fetchMock);
  render(<About />);
  expect(fetchMock).not.toHaveBeenCalled();
  openAbout();
  expect(await screen.findByText("You are viewing the running build.")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith(
    "/version.json",
    expect.objectContaining({ cache: "no-store" }),
  );
});

it("offers reload for a different revision and suppresses repeat alerts", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ ...buildInfo, revision: "b".repeat(40) }))),
      ),
  );
  render(<About />);
  openAbout();
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Reload" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Check build" }));
  expect(
    await screen.findByText("A different build is running. Save any edits, then reload to use it."),
  ).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("reports failed identity checks", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<About />);
  openAbout();
  expect(
    await screen.findByText(
      "Could not check the running build. Try again when the local service is available.",
    ),
  ).toBeTruthy();
});
