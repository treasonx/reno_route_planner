import type { Direction } from "../types";

const KEY = "passcheck.direction";

export const isDirection = (v: unknown): v is Direction => v === "reno-sac" || v === "sac-reno";

export function loadDirection(): Direction {
  try {
    const v = localStorage.getItem(KEY);
    return isDirection(v) ? v : "reno-sac";
  } catch {
    return "reno-sac";
  }
}

export function saveDirection(d: Direction): void {
  try {
    localStorage.setItem(KEY, d);
  } catch {
    // private mode / blocked storage: direction just won't persist
  }
}
