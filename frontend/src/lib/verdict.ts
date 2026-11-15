import type { VerdictLevel } from "../types";

/** CSS modifier for a verdict (color + dash pattern). */
export const verdictClass = (v: VerdictLevel): "go" | "caution" | "nogo" =>
  v === "GO" ? "go" : v === "CAUTION" ? "caution" : "nogo";

/** Non-color cue so the verdict never depends on telling red from green. */
export const verdictGlyph = (v: VerdictLevel): string =>
  v === "GO" ? "✓" : v === "CAUTION" ? "▲" : "✕";

const SEVERITY: Record<VerdictLevel, number> = { GO: 0, CAUTION: 1, "NO GO": 2 };

export const bestOf = (levels: readonly VerdictLevel[]): VerdictLevel =>
  levels.reduce<VerdictLevel>((a, b) => (SEVERITY[b] < SEVERITY[a] ? b : a), "NO GO");

const TZ = "America/Los_Angeles";
const timeFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, weekday: "short" });

/** "8:25 AM" in Pacific time. */
export const formatTime = (iso: string): string => timeFmt.format(new Date(iso));
/** "Sun" in Pacific time. */
export const formatDay = (iso: string): string => dayFmt.format(new Date(iso));
