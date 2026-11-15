import type { Direction, PlanResponse } from "./types";

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(status === 503 ? "Forecast data isn't available yet" : `Request failed (${status})`);
  }
}

export async function fetchPlan(
  direction: Direction,
  date: string | null,
  signal: AbortSignal,
): Promise<PlanResponse> {
  const params = new URLSearchParams({ direction });
  if (date) params.set("date", date);
  const res = await fetch(`/api/plan?${params.toString()}`, { signal });
  if (!res.ok) throw new ApiError(res.status);
  return (await res.json()) as PlanResponse;
}
