import { render } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePolling } from "./usePolling";

function Poller({ fn }: { fn: () => Promise<void> }) {
  usePolling(fn, 1000, [fn]);
  return null;
}

const setVisibility = (state: "visible" | "hidden") => {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
};

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility("visible");
  });
  afterEach(() => vi.useRealTimers());

  it("polls on an interval and pauses while hidden", async () => {
    const fn = vi.fn(() => Promise.resolve());
    render(<Poller fn={fn} />);
    expect(fn).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fn).toHaveBeenCalledTimes(2);

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(5000);
    expect(fn).toHaveBeenCalledTimes(2);

    setVisibility("visible"); // data is older than the interval -> refresh immediately
    await vi.advanceTimersByTimeAsync(0);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("runs a single loop when the tab flips during a pending fetch", async () => {
    let release: () => void = () => {};
    const fn = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(() => new Promise<void>((r) => (release = r)))
      .mockImplementation(() => Promise.resolve());
    render(<Poller fn={fn} />);
    expect(fn).toHaveBeenCalledTimes(1);

    // Slow first fetch: user hides and re-shows the tab while it's still pending.
    setVisibility("hidden");
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(500);
    expect(fn).toHaveBeenCalledTimes(1); // nothing new started while the tick is in flight
    release();

    await vi.advanceTimersByTimeAsync(5000);
    expect(fn).toHaveBeenCalledTimes(6); // 1 + one per interval: a second loop would double this
  });

  it("stops polling after unmount, even with a fetch in flight", async () => {
    let release: () => void = () => {};
    const fn = vi.fn(() => new Promise<void>((r) => (release = r)));
    const { unmount } = render(<Poller fn={fn} />);
    unmount();
    release();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
