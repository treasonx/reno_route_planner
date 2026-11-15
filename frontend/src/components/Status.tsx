import { formatTime } from "../lib/verdict";
import type { PlanResponse } from "../types";

const QUICKMAP_URL = "https://quickmap.dot.ca.gov";

export function StaleBanner({ plan, error }: { plan: PlanResponse; error: string | null }) {
  return (
    <div class="banner" role="status">
      <strong>As of {formatTime(plan.generated_at)} PT.</strong>{" "}
      {error ? "Can't refresh right now." : "Some data is delayed."} Check{" "}
      <a href={QUICKMAP_URL} rel="noopener noreferrer" target="_blank">
        Caltrans QuickMap
      </a>{" "}
      before you leave.
    </div>
  );
}

export function DataUnavailable({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section class="card unavailable" role="alert">
      <h2>Couldn't reach forecast sources</h2>
      <p class="muted">{message}. No verdict is shown until data is available.</p>
      <div class="actions">
        <button type="button" class="button" onClick={onRetry}>
          Retry
        </button>
        <a class="button secondary" href={QUICKMAP_URL} rel="noopener noreferrer" target="_blank">
          Open Caltrans QuickMap
        </a>
      </div>
    </section>
  );
}

export function Skeleton() {
  return (
    <div class="skeleton" aria-busy="true" aria-label="Loading">
      <div class="sk sk-pager" />
      <div class="sk sk-hero" />
      <div class="sk sk-card" />
      <div class="sk sk-days" />
    </div>
  );
}

export function Footer({ notes }: { notes: readonly string[] }) {
  return (
    <footer class="footer">
      {notes.map((n) => (
        <p key={n}>{n}</p>
      ))}
      <p>
        Guidance only. Conditions change fast in the Sierra.{" "}
        <a href={QUICKMAP_URL} rel="noopener noreferrer" target="_blank">
          Check Caltrans QuickMap
        </a>{" "}
        before you leave.
      </p>
      <p class="credits">
        Data: Caltrans, Nevada DOT, <a href="https://open-meteo.com/" rel="noopener noreferrer" target="_blank">Open-Meteo</a>{" "}
        (CC BY 4.0), Weather Underground. All times Pacific.
      </p>
    </footer>
  );
}
