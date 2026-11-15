export type SwipeDirection = "prev" | "next";

/** Pure swipe decision: horizontal, long enough, and more horizontal than vertical. */
export const detectSwipe = (dx: number, dy: number, min = 40): SwipeDirection | null =>
  Math.abs(dx) < min || Math.abs(dx) < Math.abs(dy) ? null : dx < 0 ? "next" : "prev";
