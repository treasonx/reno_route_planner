import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import plan from "./__fixtures__/plan.json";
import { App, initialHourIndex } from "./App";
import type { PlanResponse } from "./types";

const fixture = plan as PlanResponse;

function mockFetch(impl: () => Promise<Response>) {
  const fn = vi.fn((_url: string) => impl());
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

afterEach(() => {
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
    expect(screen.getByText("Next 10 days")).toBeTruthy();
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
});
