import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import plan from "./__fixtures__/plan.json";
import { App, initialHourIndex } from "./App";
import { POLL_MS } from "./hooks/usePlan";
import type { PlanResponse, RouteKey } from "./types";

const fixture = plan as PlanResponse;
const NAMES: Record<RouteKey, string> = { i80: "I-80", us50: "US-50", sr88: "SR-88" };

function mockFetch(impl: (url: string) => Promise<Response>) {
  const fn = vi.fn((url: string) => impl(url));
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  // Phone layout (3-hour pages); happy-dom's default window is desktop-wide.
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

const highway = (name: RegExp) => screen.getByRole("radio", { name });
const kicker = () => document.querySelector(".hero-kicker")?.textContent ?? "";
const pressedHour = () => document.querySelector(".hour[aria-pressed='true']")?.getAttribute("aria-label") ?? "";
const loaded = () => screen.findByRole("radiogroup", { name: "Highway" });

afterEach(() => {
  vi.useRealTimers();
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("App", () => {
  it("loads on the recommended highway and says so", async () => {
    mockFetch(() => Promise.resolve(new Response(JSON.stringify(fixture), { status: 200 })));
    render(<App />);
    await loaded();
    const best = NAMES[fixture.hours[0]!.best.route];
    expect(best).toBe("US-50");
    expect(highway(/^US-50/).getAttribute("aria-checked")).toBe("true");
    expect(highway(/^US-50/).getAttribute("aria-label")).toContain("recommended");
    expect(screen.getByText("★ Recommended leaving now")).toBeTruthy();
    expect(kicker()).toBe("US-50 · leaving now · ★ recommended");
    expect(screen.getByRole("img", { name: /US-50 elevation profile: GO/ })).toBeTruthy();
    expect(screen.getByText("10-day outlook · US-50")).toBeTruthy();
    // every verdict has a non-color glyph
    expect(highway(/^SR-88/).textContent).toContain("✕ NO GO");
  });

  it("never shows a verdict when the API fails with no prior data", async () => {
    mockFetch(() => Promise.resolve(new Response('{"status":"unavailable"}', { status: 503 })));
    render(<App />);
    expect(await screen.findByText("Couldn't reach forecast sources")).toBeTruthy();
    expect(screen.queryByText(/GO/)).toBeNull();
  });

  it("picking another highway switches the whole page and flags it as not recommended", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
    fireEvent.click(highway(/^SR-88/));

    expect(highway(/^SR-88/).getAttribute("aria-checked")).toBe("true");
    expect(kicker()).toBe("SR-88 · leaving now");
    expect(document.querySelector(".hero-title")?.textContent).toBe("NO GO");
    expect(screen.getByText("Not recommended leaving now")).toBeTruthy();
    expect(screen.getByRole("img", { name: /SR-88 elevation profile/ })).toBeTruthy();
    expect(screen.getByText("10-day outlook · SR-88")).toBeTruthy();
    expect(pressedHour()).toContain("SR-88 NO GO");

    // One tap goes back to the recommended highway.
    fireEvent.click(screen.getByRole("button", { name: "Use US-50" }));
    expect(highway(/^US-50/).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("★ Recommended leaving now")).toBeTruthy();
  });

  it("changing the time keeps the picked highway; changing the highway keeps the time", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
    fireEvent.click(highway(/^I-80/));
    fireEvent.click(screen.getByRole("button", { name: "Later hours" }));
    expect(highway(/^I-80/).getAttribute("aria-checked")).toBe("true"); // highway kept
    expect(pressedHour()).toMatch(/10 AM: I-80/);

    fireEvent.click(highway(/^SR-88/));
    expect(pressedHour()).toMatch(/10 AM: SR-88/); // time kept
  });

  it("follows the recommendation until a highway is picked; Auto resumes following", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
    // hours[2] (9 AM): the recommendation moves from US-50 to I-80.
    expect(fixture.hours[2]!.best.route).toBe("i80");
    fireEvent.click(screen.getByRole("button", { name: /Leave \w+ 9 AM/ }));
    expect(highway(/^I-80/).getAttribute("aria-checked")).toBe("true"); // followed

    fireEvent.click(highway(/^I-80/)); // pin it while it's recommended
    expect(screen.getByRole("button", { name: "Auto" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Leave \w+ 8 AM/ }));
    expect(highway(/^I-80/).getAttribute("aria-checked")).toBe("true"); // pinned stays
    fireEvent.click(screen.getByRole("button", { name: "Use US-50" }));
    fireEvent.click(screen.getByRole("button", { name: "Auto" }));
    fireEvent.click(screen.getByRole("button", { name: /Leave \w+ 9 AM/ }));
    expect(highway(/^I-80/).getAttribute("aria-checked")).toBe("true"); // following again
    expect(screen.queryByRole("button", { name: "Auto" })).toBeNull();
  });

  it("arrow keys move between highways", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
    fireEvent.keyDown(highway(/^US-50/), { key: "ArrowRight" });
    expect(highway(/^SR-88/).getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(highway(/^SR-88/));
    fireEvent.keyDown(highway(/^SR-88/), { key: "Home" });
    expect(highway(/^I-80/).getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(highway(/^I-80/));
  });

  it("swapping direction refetches and persists the direction", async () => {
    const fetchFn = mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
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
    await loaded();
    fireEvent.click(screen.getByRole("button", { name: /Swap direction/ }));
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByRole("radiogroup", { name: "Highway" })).toBeNull();
    expect(screen.queryByText(/NO GO/)).toBeNull();
  });

  it("choosing a day sends date= and opens it at 6 AM on the same highway", async () => {
    const day: PlanResponse = {
      ...fixture,
      hours: fixture.hours.slice(0, 12).map((h, i) => ({ ...h, label: i === 6 ? "6 AM" : `${i} AM` })),
    };
    const fetchFn = mockFetch((url) => ok(url.includes("date=") ? day : fixture));
    render(<App />);
    await loaded();
    fireEvent.click(highway(/^SR-88/));

    fireEvent.click(screen.getByLabelText(/^Mon 16/));
    expect(screen.getByLabelText("Loading")).toBeTruthy(); // no stale verdict while the day loads
    await waitFor(() => expect(pressedHour()).toMatch(/6 AM: SR-88/));
    expect(fetchFn.mock.calls.some(([u]) => u.includes("date=2026-11-16"))).toBe(true);
  });

  it("the 10-day strip follows the selected highway and stars its best days", async () => {
    mockFetch(() => ok(fixture));
    render(<App />);
    await loaded();
    const d0 = fixture.days[0]!;
    const name = NAMES[d0.best_route];
    expect(screen.getByLabelText(new RegExp(`^${d0.dow} ${d0.day}: ${name} ${d0.routes[d0.best_route]}, best highway`))).toBeTruthy();
    fireEvent.click(highway(/^SR-88/));
    expect(screen.getByLabelText(new RegExp(`^${d0.dow} ${d0.day}: SR-88 ${d0.routes.sr88}`))).toBeTruthy();
  });

  it("keeps the last plan visible with a stale banner when a refresh fails", async () => {
    vi.useFakeTimers();
    let calls = 0;
    mockFetch(() => (calls++ === 0 ? ok(fixture) : fail()));
    render(<App />);
    await flush();
    expect(kicker()).toContain("US-50");
    expect(screen.queryByText(/Can't refresh right now/)).toBeNull(); // server says fresh

    await advance(POLL_MS);
    await flush();
    expect(calls).toBe(2);
    expect(kicker()).toContain("US-50");
    expect(screen.getByText(/Can't refresh right now/)).toBeTruthy();
  });

  it("shows the stale banner when the server flags the plan stale", async () => {
    mockFetch(() => ok({ ...fixture, stale: true }));
    render(<App />);
    await loaded();
    expect(screen.getByText(/Some data is delayed/)).toBeTruthy();
  });

  it("keeps the selected departure and highway across an hourly refresh", async () => {
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
    fireEvent.click(highway(/^SR-88/));

    await advance(POLL_MS);
    await flush();
    expect(calls).toBe(2);
    expect(pressedHour()).toMatch(/9 AM: SR-88/); // still 9 AM on SR-88, not reset
  });
});
