import { cleanup, fireEvent, render } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SwipeDirection } from "../lib/swipe";
import { useSwipe } from "./useSwipe";

function Area({ onSwipe }: { onSwipe: (d: SwipeDirection) => void }) {
  return <div data-testid="area" {...useSwipe(onSwipe)} />;
}

afterEach(cleanup);

describe("useSwipe", () => {
  it("captures the pointer and ignores a second finger", () => {
    const onSwipe = vi.fn();
    const { getByTestId } = render(<Area onSwipe={onSwipe} />);
    const el = getByTestId("area");
    const capture = vi.fn();
    el.setPointerCapture = capture;

    fireEvent.pointerDown(el, { pointerId: 1, clientX: 200, clientY: 0 });
    expect(capture).toHaveBeenCalledWith(1);
    fireEvent.pointerDown(el, { pointerId: 2, clientX: 10, clientY: 0 }); // second finger
    fireEvent.pointerUp(el, { pointerId: 2, clientX: 300, clientY: 0 });
    expect(onSwipe).not.toHaveBeenCalled();

    fireEvent.pointerUp(el, { pointerId: 1, clientX: 100, clientY: 0 });
    expect(onSwipe).toHaveBeenCalledWith("next");
  });

  it("drops the gesture on pointercancel", () => {
    const onSwipe = vi.fn();
    const { getByTestId } = render(<Area onSwipe={onSwipe} />);
    const el = getByTestId("area");
    fireEvent.pointerDown(el, { pointerId: 1, clientX: 200, clientY: 0 });
    fireEvent.pointerCancel(el, { pointerId: 1 });
    fireEvent.pointerUp(el, { pointerId: 1, clientX: 100, clientY: 0 });
    expect(onSwipe).not.toHaveBeenCalled();
  });
});
