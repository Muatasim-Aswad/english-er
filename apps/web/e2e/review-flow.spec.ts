import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const repositoryRoot = path.resolve(import.meta.dirname, "../../..");
const hook = path.join(repositoryRoot, "integrations/voxtype/english_er_capture.py");

function transcriptCards(page: Page) {
  return page.getByRole("list", { name: /transcript list$/ }).getByRole("listitem");
}

function capture(text: string): void {
  const root = process.env.ENGLISH_ER_E2E_ROOT;
  if (root === undefined) {
    throw new Error("ENGLISH_ER_E2E_ROOT is required");
  }
  const output = execFileSync("python3", [hook], {
    input: text,
    env: {
      ...process.env,
      ENGLISH_ER_STATE_ROOT: path.join(root, "state", "english-er"),
    },
  });
  expect(output.toString()).toBe(text);
}

test("captures, corrects, auto-reviews on open, navigates, and deletes through the production UI", async ({
  page,
}) => {
  await page.goto("/");
  const captureSwitch = page.getByRole("switch", { name: "Capture off" });
  await expect(captureSwitch).toBeVisible();
  await captureSwitch.click();
  await expect(page.getByRole("switch", { name: "Capture on" })).toBeVisible();

  const older = "I has the first end-to-end fixture.";
  const newer = "This is the second end-to-end fixture.";
  capture(older);
  capture(newer);

  await expect
    .poll(
      async () => {
        const refresh = page.getByRole("button", { name: "Refresh" });
        await refresh.click();
        return transcriptCards(page).count();
      },
      { timeout: 15_000 },
    )
    .toBe(2);

  await page.getByRole("button", { name: new RegExp(newer) }).click();
  await expect(page.getByRole("heading", { name: "Corrected" })).toBeVisible();
  await expect(page.getByLabel("Corrected transcript audio", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Load existing corrected transcript audio" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark unreviewed" })).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText(older, { exact: true })).toBeVisible();
  await expect(
    page.getByText("I have the first end-to-end fixture.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark unreviewed" })).toBeVisible();

  await page.getByRole("button", { name: "Edit transcript" }).click();
  await page
    .getByRole("textbox", { name: "Transcript text" })
    .fill("I had the first end-to-end fixture.");
  await page.getByRole("button", { name: "Save and re-correct" }).click();
  await expect(page.getByRole("heading", { name: "Corrected" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Show captured text" }).click();
  await expect(page.getByText(older, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Show current transcript" }).click();
  await expect(page.getByRole("button", { name: "Mark reviewed" })).toBeVisible();
  await page.getByRole("button", { name: "Mark reviewed" }).click();

  await page.getByRole("button", { name: "All transcripts" }).click();
  await expect(transcriptCards(page)).toHaveCount(2);
  await page.getByRole("button", { name: "To review" }).click();
  await expect(page.getByText("Nothing here")).toBeVisible();
  await page.getByRole("button", { name: "All transcripts" }).click();
  await expect(transcriptCards(page)).toHaveCount(2);

  await page.getByRole("button", { name: new RegExp(newer) }).click();
  await page.getByRole("button", { name: "Delete permanently" }).click();
  await page.getByRole("button", { name: "Yes, delete permanently" }).click();
  await expect(page.getByRole("button", { name: new RegExp(newer) })).toHaveCount(0);
  await expect(transcriptCards(page)).toHaveCount(1);
});
