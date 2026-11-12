import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { TranscriptDetail, TranscriptSummary } from "../features/transcripts/api";

const firstId = "0198f100-0000-7000-8000-000000000001";
const secondId = "0198f100-0000-7000-8000-000000000002";
const capturedAt = "2026-08-30T12:00:00Z";

const firstSummary: TranscriptSummary = {
  id: firstId,
  source: "voxtype",
  preview: "I has a useful example.",
  captured_at: capturedAt,
  reviewed_at: null,
  status: "completed",
  attempt_count: 1,
  last_error: null,
};

const secondSummary: TranscriptSummary = {
  ...firstSummary,
  id: secondId,
  preview: "The second transcript.",
};

const firstDetail: TranscriptDetail = {
  id: firstId,
  source: "voxtype",
  preview: firstSummary.preview,
  original_text: "I has a useful example.",
  transcript_text: "I has a useful example.",
  text_revision: 1,
  captured_at: capturedAt,
  reviewed_at: null,
  status: "completed",
  attempt_count: 1,
  last_error: null,
  created_at: capturedAt,
  updated_at: capturedAt,
  correction: {
    corrected_text: "I have a useful example.",
    corrections: [{ wrong: "has", correct: "have" }],
    overall_observation: "Use have with the first-person subject.",
    audio_available: false,
    provider: "codex",
    model: "gpt-5.6-luna",
    prompt_version: "1",
    input_revision: 1,
    created_at: capturedAt,
  },
};

type ApiOptions = {
  items?: TranscriptSummary[];
  nextCursor?: string | null;
  details?: Record<string, TranscriptDetail>;
  listStatus?: number;
  detailStatus?: number;
  actionStatus?: number;
  backgroundListGate?: Promise<void>;
  audioGate?: Promise<void>;
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(
    status === 204
      ? null
      : JSON.stringify(
          status >= 400
            ? { error: { status, request_id: "test-request", ...(body as object) } }
            : body,
        ),
    {
      status,
      ...(status === 204 ? {} : { headers: { "Content-Type": "application/json" } }),
    },
  );
}

function requestUrl(input: RequestInfo | URL): URL {
  const value = input instanceof Request ? input.url : input.toString();
  return new URL(value, "http://localhost");
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  return input instanceof Request ? input.method : (init?.method ?? "GET");
}

function installApi(options: ApiOptions = {}) {
  const details = options.details ?? { [firstId]: firstDetail };
  let listCallCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = requestMethod(input, init);

    if (url.pathname === "/api/v1/health") {
      return jsonResponse({ api: "ok", database: "ok" });
    }
    if (url.pathname === "/api/v1/capture" && method === "GET") {
      return jsonResponse({ enabled: false });
    }
    if (url.pathname === "/api/v1/capture" && method === "PUT") {
      return options.actionStatus === undefined
        ? jsonResponse({ enabled: true })
        : jsonResponse(
            { code: "capture_error", message: "Capture is locked." },
            options.actionStatus,
          );
    }
    if (url.pathname === "/api/v1/transcripts" && method === "GET") {
      listCallCount += 1;
      if (listCallCount > 1) {
        await options.backgroundListGate;
      }
      if (options.listStatus !== undefined) {
        return jsonResponse(
          { code: "list_error", message: "Queue unavailable." },
          options.listStatus,
        );
      }
      return jsonResponse({
        items: options.items ?? [firstSummary],
        metadata: { next_cursor: options.nextCursor ?? null },
      });
    }

    const id = url.pathname.split("/")[4];
    if (id !== undefined && url.pathname.endsWith("/review") && method === "PUT") {
      if (options.actionStatus !== undefined) {
        return jsonResponse(
          { code: "review_error", message: "Review was rejected." },
          options.actionStatus,
        );
      }
      const detail = details[id] ?? firstDetail;
      return jsonResponse({ ...detail, reviewed_at: capturedAt });
    }
    if (id !== undefined && url.pathname.endsWith("/text") && method === "PUT") {
      if (options.actionStatus !== undefined) {
        return jsonResponse(
          { code: "revision_conflict", message: "The transcript changed." },
          options.actionStatus,
        );
      }
      const detail = details[id] ?? firstDetail;
      const request = input instanceof Request ? input : new Request(url, init);
      const body = (await request.clone().json()) as { text: string };
      return jsonResponse({
        ...detail,
        transcript_text: body.text,
        preview: body.text,
        text_revision: detail.text_revision + 1,
        reviewed_at: null,
        status: "pending",
        attempt_count: 0,
        correction: null,
      });
    }
    if (id !== undefined && url.pathname.endsWith("/audio") && method === "POST") {
      await options.audioGate;
      return new Response(new Uint8Array([82, 73, 70, 70]), {
        headers: { "Content-Type": "audio/wav" },
      });
    }
    if (id !== undefined && url.pathname.endsWith("/retry") && method === "POST") {
      const detail = details[id] ?? firstDetail;
      return jsonResponse({
        id: detail.id,
        source: detail.source,
        preview: detail.transcript_text,
        captured_at: detail.captured_at,
        reviewed_at: detail.reviewed_at,
        status: "pending",
        attempt_count: detail.attempt_count,
        last_error: null,
      });
    }
    if (id !== undefined && url.pathname === `/api/v1/transcripts/${id}` && method === "DELETE") {
      return jsonResponse(null, 204);
    }
    if (id !== undefined && url.pathname === `/api/v1/transcripts/${id}` && method === "GET") {
      if (options.detailStatus !== undefined || details[id] === undefined) {
        return jsonResponse(
          { code: "not_found", message: "Transcript not found." },
          options.detailStatus ?? 404,
        );
      }
      return jsonResponse(details[id]);
    }
    return jsonResponse({ code: "unexpected", message: `${method} ${url.pathname}` }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("review workspace", () => {
  it("loads the unreviewed-completed view through typed query parameters", async () => {
    const fetchMock = installApi();
    render(<App />);

    expect(await screen.findByText(firstSummary.preview)).toBeTruthy();
    expect(screen.getByRole("button", { name: "To review" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByRole("switch", { name: "Capture off" })).toBeTruthy();

    const listCall = fetchMock.mock.calls.find(
      ([input]) => requestUrl(input).pathname === "/api/v1/transcripts",
    );
    expect(listCall).toBeDefined();
    const url = requestUrl(listCall![0]);
    expect(url.searchParams.get("status")).toBe("completed");
    expect(url.searchParams.get("reviewed")).toBe("unreviewed");
    expect(url.searchParams.get("limit")).toBe("20");
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).pathname.endsWith("/review")),
    ).toBe(false);
  });

  it("requests the all and failed views with their contract filters", async () => {
    const fetchMock = installApi();
    render(<App />);
    await screen.findByText(firstSummary.preview);

    fireEvent.click(screen.getByRole("button", { name: "All transcripts" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "All transcripts" }).getAttribute("aria-pressed"),
      ).toBe("true"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Failed" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Failed" }).getAttribute("aria-pressed")).toBe(
        "true",
      ),
    );

    const listUrls = fetchMock.mock.calls
      .map(([input]) => requestUrl(input))
      .filter((url) => url.pathname === "/api/v1/transcripts");
    expect(listUrls.some((url) => url.searchParams.get("status") === null)).toBe(true);
    expect(listUrls.some((url) => url.searchParams.get("status") === "failed")).toBe(true);
  });

  it("uses the opaque cursor to append another page", async () => {
    const fetchMock = installApi({ nextCursor: "opaque:cursor" });
    render(<App />);
    await screen.findByText(firstSummary.preview);

    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([input]) => requestUrl(input));
      expect(calls.some((url) => url.searchParams.get("cursor") === "opaque:cursor")).toBe(true);
    });
  });

  it("renders original text, corrected text, pairs, and observation after selection", async () => {
    installApi();
    render(<App />);
    const transcriptButton = await screen.findByRole("button", { name: /I has a useful example/ });

    transcriptButton.focus();
    expect(document.activeElement).toBe(transcriptButton);
    fireEvent.click(transcriptButton);

    expect(await screen.findByText("I have a useful example.")).toBeTruthy();
    expect(screen.getByText("Use have with the first-person subject.")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Overall observation" })).toBeNull();
    expect(screen.queryByText("Observation")).toBeNull();
    const observation = screen.getByText("Use have with the first-person subject.");
    expect(observation.previousElementSibling).toBe(
      screen.getByRole("heading", { name: /^Corrections/ }).parentElement,
    );
    expect(screen.getByText("has")).toBeTruthy();
    expect(screen.getByText("have")).toBeTruthy();
  });

  it("prepares corrected audio when the card opens and shows native controls", async () => {
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:corrected");
    let releaseAudio!: () => void;
    const audioGate = new Promise<void>((resolve) => {
      releaseAudio = resolve;
    });
    const fetchMock = installApi({ audioGate });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    await screen.findByText("I have a useful example.");

    const processingButton = await screen.findByRole("button", {
      name: "Preparing corrected transcript audio",
    });
    expect(processingButton.dataset.tone).toBe("processing");
    await act(async () => {
      releaseAudio();
      await audioGate;
    });

    const player = await screen.findByLabelText("Corrected transcript audio");
    expect(player.getAttribute("controls")).not.toBeNull();
    expect(player.getAttribute("src")).toBe("blob:corrected");
    expect((player as HTMLAudioElement).playbackRate).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Set playback speed to 0.75×" }));
    expect((player as HTMLAudioElement).playbackRate).toBe(0.75);
    expect(
      screen
        .getByRole("button", { name: "Set playback speed to 0.75×" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Load existing corrected transcript audio" }).dataset.tone,
    ).toBe("existing");
    const audioCall = fetchMock.mock.calls.find(([input]) =>
      requestUrl(input).pathname.endsWith("/audio"),
    );
    expect(audioCall).toBeDefined();
    const request =
      audioCall![0] instanceof Request
        ? audioCall![0]
        : new Request(requestUrl(audioCall![0]), audioCall![1]);
    expect(await request.clone().json()).toEqual({ expected_revision: 1 });
  });

  it("marks completed transcripts reviewed on intentional open and advances without another review action", async () => {
    const secondDetail: TranscriptDetail = {
      ...firstDetail,
      id: secondId,
      preview: secondSummary.preview,
      original_text: "The second transcript.",
      transcript_text: "The second transcript.",
      correction: { ...firstDetail.correction!, corrected_text: "The second transcript." },
    };
    const fetchMock = installApi({
      items: [firstSummary, secondSummary],
      details: { [firstId]: firstDetail, [secondId]: secondDetail },
    });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    await screen.findByText("I have a useful example.");

    expect(screen.getByRole("button", { name: /I has a useful example/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("The second transcript.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /I has a useful example/ })).toBeNull();
    expect(
      fetchMock.mock.calls.filter(([input]) => requestUrl(input).pathname.endsWith("/review")),
    ).toHaveLength(2);
  });

  it("navigates reviewed transcripts without changing their review state", async () => {
    const reviewedFirst = { ...firstSummary, reviewed_at: capturedAt };
    const reviewedSecond = { ...secondSummary, reviewed_at: capturedAt };
    const reviewedFirstDetail = { ...firstDetail, reviewed_at: capturedAt };
    const reviewedSecondDetail: TranscriptDetail = {
      ...firstDetail,
      id: secondId,
      preview: secondSummary.preview,
      original_text: "The second transcript.",
      transcript_text: "The second transcript.",
      reviewed_at: capturedAt,
      correction: { ...firstDetail.correction!, corrected_text: "The second transcript." },
    };
    const fetchMock = installApi({
      items: [reviewedFirst, reviewedSecond],
      details: { [firstId]: reviewedFirstDetail, [secondId]: reviewedSecondDetail },
    });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "All transcripts" }));
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    await screen.findByText("I have a useful example.");

    expect(
      within(screen.getByRole("group", { name: "Review actions" }))
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["Next", "Previous", "Mark unreviewed", "Delete permanently"]);
    expect(screen.getByRole("button", { name: "Previous" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("The second transcript.")).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(
        ([input], index) =>
          index > 0 &&
          requestUrl(input).pathname.endsWith("/review") &&
          requestMethod(input) === "PUT",
      ),
    ).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("I have a useful example.")).toBeTruthy();
  });

  it("toggles capture and exposes action failures", async () => {
    installApi({ actionStatus: 409 });
    render(<App />);
    fireEvent.click(await screen.findByRole("switch", { name: "Capture off" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Capture change failed: Capture is locked.",
    );
  });

  it("edits the transcript and submits its expected revision for re-correction", async () => {
    const fetchMock = installApi();
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    await screen.findByText("I have a useful example.");

    fireEvent.click(screen.getByRole("button", { name: "Edit transcript" }));
    const editor = screen.getByRole("textbox", { name: "Transcript text" });
    fireEvent.change(editor, { target: { value: "I had a useful example." } });
    fireEvent.click(screen.getByRole("button", { name: "Save and re-correct" }));

    expect(await screen.findByRole("heading", { name: "Correction in progress" })).toBeTruthy();
    expect(screen.getAllByText("I had a useful example.")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Show captured text" }));
    expect(screen.getByText("I has a useful example.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Show current transcript" })).toBeTruthy();
    const editCall = fetchMock.mock.calls.find(
      ([input], index) =>
        index > 0 && requestUrl(input).pathname.endsWith("/text") && requestMethod(input) === "PUT",
    );
    expect(editCall).toBeDefined();
    const request =
      editCall![0] instanceof Request
        ? editCall![0]
        : new Request(requestUrl(editCall![0]), editCall![1]);
    expect(await request.clone().json()).toEqual({
      text: "I had a useful example.",
      expected_revision: 1,
    });
  });

  it("only offers retry for failed transcripts and confirms permanent deletion", async () => {
    const failedSummary: TranscriptSummary = {
      ...firstSummary,
      status: "failed",
      last_error: "Provider timed out.",
    };
    const failedDetail: TranscriptDetail = {
      ...firstDetail,
      status: "failed",
      last_error: "Provider timed out.",
      correction: null,
    };
    const fetchMock = installApi({ items: [failedSummary], details: { [firstId]: failedDetail } });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    expect(await screen.findByRole("button", { name: "Retry correction" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
    const dialog = screen.getByRole("alertdialog", { name: "Delete this transcript?" });
    expect(dialog).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete permanently" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input]) =>
            requestUrl(input).pathname.endsWith(firstId) && requestMethod(input) === "DELETE",
        ),
      ).toBe(true),
    );
  });

  it("shows loading and empty states", async () => {
    installApi({ items: [] });
    render(<App />);
    expect(screen.getByText("Loading transcripts…")).toBeTruthy();
    expect(await screen.findByText("Nothing here")).toBeTruthy();
  });

  it("distinguishes an unavailable API from another list error", async () => {
    installApi({ listStatus: 503 });
    const firstRender = render(<App />);
    expect(await screen.findAllByText("API unavailable")).not.toHaveLength(0);
    firstRender.unmount();

    installApi({ listStatus: 500 });
    render(<App />);
    expect(await screen.findByText("Couldn’t load transcripts")).toBeTruthy();
  });

  it("reports a stale selection when detail returns 404", async () => {
    installApi({ detailStatus: 404 });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    expect(await screen.findByText("Selection is stale")).toBeTruthy();
  });

  it("polls every five seconds only while visible and stops after unmount", async () => {
    vi.useFakeTimers();
    let visibility: DocumentVisibilityState = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
    const fetchMock = installApi();
    const rendered = render(<App />);
    await act(async () => Promise.resolve());
    const listCalls = () =>
      fetchMock.mock.calls.filter(([input]) => requestUrl(input).pathname === "/api/v1/transcripts")
        .length;
    const initial = listCalls();

    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(listCalls()).toBeGreaterThan(initial);
    visibility = "hidden";
    fireEvent(document, new Event("visibilitychange"));
    const hiddenCount = listCalls();
    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    expect(listCalls()).toBe(hiddenCount);

    rendered.unmount();
    visibility = "visible";
    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    expect(listCalls()).toBe(hiddenCount);
  });

  it("keeps automatic polling visually quiet", async () => {
    vi.useFakeTimers();
    let releasePoll: (() => void) | undefined;
    const backgroundListGate = new Promise<void>((resolve) => {
      releasePoll = resolve;
    });
    installApi({ backgroundListGate });
    render(<App />);
    await act(async () => Promise.resolve());
    expect(screen.getByText(firstSummary.preview)).toBeTruthy();

    await act(async () => vi.advanceTimersByTimeAsync(5_000));

    const refresh = screen.getByRole("button", { name: "Refresh" });
    expect(refresh.hasAttribute("disabled")).toBe(false);
    expect(screen.queryByText("Refreshing transcript list.")).toBeNull();

    await act(async () => releasePoll?.());
  });
  it("ignores a previous selection's late failure", async () => {
    const secondDetail: TranscriptDetail = {
      ...firstDetail,
      id: secondId,
      preview: secondSummary.preview,
      original_text: "The second transcript.",
      transcript_text: "The second transcript.",
      reviewed_at: capturedAt,
      correction: {
        ...firstDetail.correction!,
        corrected_text: "The second corrected transcript.",
      },
    };
    const fetchMock = installApi({
      items: [firstSummary, secondSummary],
      details: { [firstId]: firstDetail, [secondId]: secondDetail },
    });
    const implementation = fetchMock.getMockImplementation()!;
    let release: ((response: Response) => void) | undefined;
    const delayed = new Promise<Response>((resolve) => {
      release = resolve;
    });
    fetchMock.mockImplementation((input, init) =>
      requestUrl(input).pathname === `/api/v1/transcripts/${firstId}` &&
      requestMethod(input, init) === "GET"
        ? delayed
        : implementation(input, init),
    );
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /I has a useful example/ }));
    fireEvent.click(screen.getByRole("button", { name: /The second transcript/ }));
    expect(await screen.findByText("The second corrected transcript.")).toBeTruthy();
    await act(async () => {
      release?.(jsonResponse({ code: "not_found", message: "Transcript not found." }, 404));
    });
    expect(screen.queryByText("Selection is stale")).toBeNull();
    expect(screen.getByText("The second corrected transcript.")).toBeTruthy();
  });
});
