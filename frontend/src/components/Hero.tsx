import { verdictClass, verdictGlyph } from "../lib/verdict";
import type { HourOut } from "../types";

export function Hero({ hour, stale }: { hour: HourOut; stale: boolean }) {
  const v = hour.best.verdict;
  const kicker = v === "NO GO" ? `Leaving ${hour.label.toLowerCase()}` : `Best route leaving ${hour.label.toLowerCase()}`;
  return (
    <section class={`hero ${verdictClass(v)}${stale ? " is-stale" : ""}`} aria-live="polite">
      <p class="eyebrow hero-kicker">{kicker}</p>
      <h2 class="hero-title" key={hour.depart}>{hour.hero.title}</h2>
      <p class="hero-sub">
        <span aria-hidden="true">{verdictGlyph(v)} </span>
        {hour.hero.sub}
      </p>
      <p class="hero-body">{hour.hero.body}</p>
    </section>
  );
}
