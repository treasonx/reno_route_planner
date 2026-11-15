import type { Direction } from "../types";

const LABEL: Record<Direction, string> = {
  "reno-sac": "Reno → Sacramento",
  "sac-reno": "Sacramento → Reno",
};

export function Header({ direction, onSwap }: { direction: Direction; onSwap: () => void }) {
  return (
    <header class="header">
      <h1 class="brand">Pass Check</h1>
      <button type="button" class="direction" onClick={onSwap} aria-label={`${LABEL[direction]}. Swap direction`}>
        <span>{LABEL[direction]}</span>
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" class="icon">
          <path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3" />
        </svg>
      </button>
    </header>
  );
}
