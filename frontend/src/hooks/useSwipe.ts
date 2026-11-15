import { useRef } from "preact/hooks";

import { detectSwipe, type SwipeDirection } from "../lib/swipe";

/** Pointer-event swipe handlers; pair with ``touch-action: pan-y`` so vertical scroll works. */
export function useSwipe(onSwipe: (dir: SwipeDirection) => void) {
  const start = useRef<{ x: number; y: number; id: number } | null>(null);
  return {
    onPointerDown: (e: PointerEvent) => {
      start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
    },
    onPointerUp: (e: PointerEvent) => {
      const s = start.current;
      start.current = null;
      if (!s || s.id !== e.pointerId) return;
      const dir = detectSwipe(e.clientX - s.x, e.clientY - s.y);
      if (dir) onSwipe(dir);
    },
    onPointerCancel: () => {
      start.current = null;
    },
  };
}
