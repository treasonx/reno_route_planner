import type { HourOut, PlanResponse, RouteKey } from "../types";

interface Props {
  plan: PlanResponse;
  hour: HourOut;
  selected: RouteKey;
  recommended: RouteKey | null;
  pinned: boolean;
  onUse: (route: RouteKey) => void;
  onAuto: () => void;
}

/** Always states whether the selected highway is the recommended one for this departure. */
export function RecommendationBanner({ plan, hour, selected, recommended, pinned, onUse, onAuto }: Props) {
  const leaving = hour.label === "Now" ? "now" : hour.label;

  if (recommended === null) {
    return (
      <div class="rec rec-none" role="status">
        <div class="rec-text">
          <p class="rec-title">No highway is recommended leaving {leaving}</p>
          <p class="rec-sub">All three are NO GO at this time.</p>
        </div>
      </div>
    );
  }

  if (selected === recommended) {
    return (
      <div class="rec rec-yes" role="status">
        <div class="rec-text">
          <p class="rec-title">★ Recommended leaving {leaving}</p>
          <p class="rec-sub">
            {pinned
              ? `${plan.corridors[selected].name} stays selected as you change the time.`
              : "Follows the best highway as you change the time."}
          </p>
        </div>
        {pinned && (
          <button type="button" class="rec-action secondary" onClick={onAuto}>
            Auto
          </button>
        )}
      </div>
    );
  }

  const rec = plan.corridors[recommended].name;
  return (
    <div class="rec rec-no" role="status">
      <div class="rec-text">
        <p class="rec-title">Not recommended leaving {leaving}</p>
        <p class="rec-sub">
          {rec} is {hour.routes[recommended].verdict} at this time.
        </p>
      </div>
      <button type="button" class="rec-action" onClick={() => onUse(recommended)}>
        Use {rec}
      </button>
    </div>
  );
}
