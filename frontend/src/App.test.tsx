import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import plan from "./__fixtures__/plan.json";
import { App, initialHourIndex } from "./App";
import { POLL_MS } from "./hooks/usePlan";
import type { PlanResponse } from "./types";

const fixture = plan as PlanResponse;

function mockFetch(impl: (url: string) => Promise<Response>) {
  const fn = vi.fn((url: string) => impl(url));
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  // Phone layout (tabs + 3-hour pages); happy-dom's default window is desktop-wide.
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

/** Minimal Response stand-in: resolves on microtasks only, so it works under fake timers. */
const ok = (body: PlanResponse) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
const fail = () => Promise.resolve({ ok: false, status: 503 } as unknown as Response);
const never = () => new Promise<Response>(() => {});

/** Lets pending fetch/json promises settle and Preact re-render under fake timers. */
const advance = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
const flush = () => advance(0);

afterEach(() => {
  vi.useRealTimers();
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("App", () => {
  it("renders the recommendation, routes and 10-day strip", async () => {
    mockFetch(() => Promise.resolve(new Response(JSON.stringify(fixture), { status: 200 })));
    render(<App />);
    expect(await screen.findByText("Take US-50")).toBeTruthy();
    expect(screen.getByRole("tab", { name: /US-50/ }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("img", { name: /US-50 elevation profile: GO/ })).toBeTruthy();
    expect(screen.getByText("10-day outlook")).toBeTruthy();
    // verdict always has a non-color glyph
    expect(screen.getByRole("tab", { name: /SR-88/ }).textContent).toContain("✕ NO GO");
  });

  it("never shows a verdict when the API fails with no prior data", async () => {
    mockFetch(() => Promise.resolve(new Response('{"status":"unavailable"}', { status: 503 })));
    render(<App />);
    expect(await screen.findByText("Couldn't reach forecast sources")).toBeTruthy();
    expect(screen.queryByText(/GO/)).toBeNull();
  });

  it("selecting a later hour updates the hero; swapping direction refetches", async () => {
    const fetchFn = mockFetch(() => Promise.resolve(new Response(JSON.stringify(fixture), { status: 200 })));
    render(<App />);
    await screen.findByText("Take US-50");
    fireEvent.click(screen.getByRole("button", { name: "Later hours" }));
    await waitFor(() => expect(screen.getByText(fixture.hours[3]!.hero.title)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Swap direction/ }));
    await waitFor(() => expect(fetchFn.mock.calls.some((c) => String(c[0]).includes("sac-reno"))).toBe(true));
    expect(localStorage.getItem("passcheck.direction")).toBe("sac-reno");
  });

  it("opens future days at 6 AM", () => {
    const day = { ...fixture, hours: fixture.hours.map((h, i) => ({ ...h, label: `${i} AM` })) };
    expect(initialHourIndex(day, "2026-11-18")).toBe(6);
    expect(initialHourIndex(fixture, null)).toBe(0);
  });

  it("shows the skeleton, not the old verdicts, immediately after a swap", async () => {
    mockFetch((url) => (url.includes("sac-reno") ? never() : ok(fixture)));
    render(<App />);
    await screen.findByText("Take US-50");
    fireEvent.click(screen.getByRole("button", { name: /Swap direction/ }));
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText("Take US-50")).toBeNull();
    expect(screen.queryByText(/NO GO/)).toBeNull();
  });

  it("choosing a day sends date= and opens it at 6 AM", async () => {
    const day: PlanResponse = {
      ...fixture,
      hours: fixture.hours.slice(0, 12).map((h, i) => ({
        ...h,
        label: i === 6 ? "6 AM" : `${i} AM`,
        hero: { ...h.hero, title: i === 6 ? "Six AM pick" : `Hour ${i}` },
      })),
    };
    const fetchFn = mockFetch((url) => ok(url.includes("date=") ? day : fixture));
    render(<App />);
    await screen.findByText("Take US-50");

    // Day controls may be buttons or radios; their accessible name starts with "Mon 16".
    fireEvent.click(screen.getByLabelText(/^Mon 16/));
    expect(screen.getByLabelText("Loading")).toBeTruthy(); // no stale verdict while the day loads
    expect(await screen.findByText("Six AM pick")).toBeTruthy();
    expect(fetchFn.mock.calls.some(([u]) => u.includes("date=2026-11-16"))).toBe(true);
  });

  it("keeps the last plan visible with a stale banner when a refresh fails", async () => {
    vi.useFakeTimers();
    let calls = 0;
    mockFetch(() => (calls++ === 0 ? ok(fixture) : fail()));
    render(<App />);
    await flush();
    expect(screen.getByText("Take US-50")).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull(); // server says fresh -> no banner

    await advance(POLL_MS);
    await flush();
    expect(calls).toBe(2);
    expect(screen.getByText("Take US-50")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Can't refresh right now");
  });

  it("shows the stale banner when the server flags the plan stale", async () => {
    mockFetch(() => ok({ ...fixture, stale: true }));
    render(<App />);
    await screen.findByText("Take US-50");
    expect(screen.getByRole("status").textContent).toContain("Some data is delayed");
  });

  it("keeps the selected departure across an hourly refresh", async () => {
    vi.useFakeTimers();
    // Next refresh crosses the hour: the old "Now" rolls off and 8 AM becomes "Now".
    const rolled: PlanResponse = {
      ...fixture,
      hours: fixture.hours.slice(1).map((h, i) => (i === 0 ? { ...h, label: "Now" } : h)),
    };
    let calls = 0;
    mockFetch(() => ok(calls++ === 0 ? fixture : rolled));
    render(<App />);
    await flush();
    fireEvent.click(screen.getByRole("button", { name: /Leave \w+ 9 AM/ }));
    expect(screen.getByText(fixture.hours[2]!.hero.title)).toBeTruthy(); // "Take I-80"
    fireEvent.click(screen.getByRole("tab", { name: /SR-88/ }));

    await advance(POLL_MS);
    await flush();
    expect(calls).toBe(2);
    expect(screen.getByText("Take I-80")).toBeTruthy(); // still 9 AM, not reset to Now
    expect(screen.getByRole("tab", { name: /SR-88/ }).getAttribute("aria-selected")).toBe("true");
  });

  it("moves between route tabs with the arrow keys", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await screen.findByText("Take US-50");
    const us50 = screen.getByRole("tab", { name: /US-50/ });
    expect(us50.getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(us50, { key: "ArrowRight" });
    const sr88 = screen.getByRole("tab", { name: /SR-88/ });
    expect(sr88.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(sr88);

    fireEvent.keyDown(sr88, { key: "ArrowLeft" });
    fireEvent.keyDown(screen.getByRole("tab", { name: /US-50/ }), { key: "ArrowLeft" });
    const i80 = screen.getByRole("tab", { name: /I-80/ });
    expect(i80.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(i80);
  });
});
