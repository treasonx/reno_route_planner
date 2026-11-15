import { describe, expect, it } from "vitest";

import { isDirection } from "./storage";
import { detectSwipe } from "./swipe";
import { bestOf, verdictClass, verdictGlyph } from "./verdict";

describe("detectSwipe", () => {
  it.each([
    [-60, 5, "next"],
    [60, -5, "prev"],
    [-30, 0, null], // too short
    [-60, 80, null], // mostly vertical (scrolling)
    [0, 0, null],
  ] as const)("dx=%d dy=%d -> %s", (dx, dy, expected) => {
    expect(detectSwipe(dx, dy)).toBe(expected);
  });
});

describe("isDirection", () => {
  it("accepts only the two directions", () => {
    expect(isDirection("reno-sac")).toBe(true);
    expect(isDirection("sac-reno")).toBe(true);
    expect(isDirection("la-sf")).toBe(false);
    expect(isDirection(null)).toBe(false);
  });
});

describe("verdict helpers", () => {
  it("pairs every verdict with a non-color glyph", () => {
    expect(verdictGlyph("GO")).toBe("✓");
    expect(verdictGlyph("CAUTION")).toBe("▲");
    expect(verdictGlyph("NO GO")).toBe("✕");
    expect(verdictClass("NO GO")).toBe("nogo");
  });

  it("picks the best verdict in a chunk", () => {
    expect(bestOf(["NO GO", "CAUTION", "NO GO"])).toBe("CAUTION");
    expect(bestOf(["NO GO"])).toBe("NO GO");
    expect(bestOf([])).toBe("NO GO"); // empty never reads as GO
  });
});
