import { cleanup, render, waitFor } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";

import plan from "../__fixtures__/plan.json";
import type { Direction, PlanResponse } from "../types";
import { type PlanState, usePlan } from "./usePlan";

const fixture = plan as PlanResponse;

type Seen = { direction: Direction; state: PlanState };

function Probe({ direction, seen }: { direction: Direction; seen: Seen[] }) {
  const { state } = usePlan(direction, null);
  seen.push({ direction, state });
  return null;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("usePlan", () => {
  it("never renders the previous direction's plan under a new direction", async () => {
    // Echo the requested direction back so we can tell plans apart.
    vi.stubGlobal("fetch", (url: string) => {
      const direction = new URL(url, "http://x").searchParams.get("direction");
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ...fixture, direction }) });
    });
    const seen: Seen[] = [];
    const { rerender } = render(<Probe direction="reno-sac" seen={seen} />);
    await waitFor(() => expect(seen.at(-1)?.state.status).toBe("ready"));

    rerender(<Probe direction="sac-reno" seen={seen} />);
    // First render after the swap must already read as loading, not the old plan.
    expect(seen.at(-1)).toMatchObject({ direction: "sac-reno", state: { status: "loading" } });
    await waitFor(() => expect(seen.at(-1)?.state).toMatchObject({ status: "ready", plan: { direction: "sac-reno" } }));

    for (const { direction, state } of seen) {
      if (state.status === "ready") expect(state.plan.direction).toBe(direction);
    }
  });
});
