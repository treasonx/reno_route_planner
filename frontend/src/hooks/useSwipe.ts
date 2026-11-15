import { useRef } from "preact/hooks";

import { detectSwipe, type SwipeDirection } from "../lib/swipe";

/**
 * Pointer-event swipe handlers; pair with ``touch-action: pan-y`` so vertical scroll works.
 *
 * The first pointer is captured so a swipe that ends outside the element still lands here;
 * extra pointers (a second finger) are ignored until the first one lifts or is cancelled.
 */
export function useSwipe(onSwipe: (dir: SwipeDirection) => void) {
  const start = useRef<{ x: number; y: number; id: number } | null>(null);
  return {
    onPointerDown: (e: PointerEvent) => {
      if (start.current) return; // one gesture at a time
      start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
      try {
        (e.currentTarget as Element | null)?.setPointerCapture(e.pointerId);
      } catch {
        // capture is best-effort (e.g. pointer already released)
      }
    },
    onPointerUp: (e: PointerEvent) => {
      const s = start.current;
      if (!s || s.id !== e.pointerId) return;
      start.current = null;
      const dir = detectSwipe(e.clientX - s.x, e.clientY - s.y);
      if (dir) onSwipe(dir);
    },
    onPointerCancel: (e: PointerEvent) => {
      if (start.current?.id === e.pointerId) start.current = null;
    },
  };
}
