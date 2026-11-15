---
date: 2026-11-15
topic: pass-check
---

# Pass Check: Sierra crossing go/no-go

## What We're Building

A mobile-first web app (installable to the home screen, also works on desktop) that tells a driver whether it's safe to cross the Sierra between Reno and Sacramento, in either direction, on one of three routes: **I-80 (Donner Summit)**, **US-50 (Spooner + Echo Summit)**, **SR-88 (Carson Pass)**.

The user picks a **departure time** (now, any hour in the next 24 hours, or any hour on one of the next 10 days). The app answers in one line, "Take US-50 · GO for departures until 12 PM", and shows each route's elevation profile colored by the conditions the driver will meet *when they reach each stretch*.

It's for personal use: the owner, family and friends. No accounts, no app stores.

Mockups (C2 is the chosen phone design; desktop below it): https://claude.ai/artifact/DttPZoFQ9FFxdJNZ3NwNs8

## Why This Approach

We compared three home screens: (A) compare all routes with heatmap grids, (B) one route at a time with tabs, (C) "just tell me" with a single answer. **C won on simplicity.** It then picked up a route-profile graphic, dark mode, and a departure-time picker. Rejected along the way:
- **Separate "Other routes" list plus a graphic:** merged into one route card.
- **Horizontal scrolling hour strip:** rejected outright.
- **A grid showing all 24 hours at once:** too busy.
- **Address entry:** unnecessary, since the three routes and the two endpoints cover the use case.

## Key Decisions

**Verdict model:** three states, GO / CAUTION / NO GO. The word always appears with the color, never color alone.

| Verdict | Triggers |
|---|---|
| **NO GO** | Any Caltrans chain control (R1/R2/R3) or a road closure. Or any forecast snow accumulation at a summit (≥ ½ in) with temp ≤ 34°F. |
| **CAUTION** | Black ice risk: below 34°F after recent rain, melt or high humidity, mostly overnight and early morning. Or a 20–40% chance of snow. Or freezing rain anywhere on the route. Or a Caltrans icy-spots advisory. |
| **GO** | None of the above. |

- **Live Caltrans data always overrides the forecast** for the hours it covers.
- **Departure-time semantics:** each segment is evaluated at the time the driver will *arrive* at it, not the time they leave. Shown as "Leave 1 PM → Echo Summit around 2:25 PM".
- **Recommended route** = the best verdict at that departure time. Ties go to the route that stays GO the longest.
- **The hero card** says one of three things: "Take X", "Careful on X", or "Don't cross" with a pointer to the next clear day.

**UX:**
- **Dark theme.**
- **Direction toggle** between Reno → Sacramento and Sacramento → Reno. No address entry.
- **"Leave at" pager:** three hours per page on phone, six per page on desktop, with ‹ › arrows. A thin chunk bar under it shows each page's best verdict.
- **One "All routes" card:**
  - Phone: route buttons, each with its status. Tap a button or swipe the profile to switch routes. One caption plus the summit arrival time.
  - Desktop: all three profiles stacked, with the best route highlighted.
- **10-day strip:** each day shows its worst verdict. Tapping a day loads that day's hours into the same pager.
- **Footer:** "Guidance only" plus a link to Caltrans QuickMap.
- **Responsive:** one page; the desktop's two columns stack on narrow screens.

**Data sources:**
- **Caltrans** for live chain controls, closures and advisories.
- **Weather Underground** for forecasts, using the owner's API key.
- **NWS (api.weather.gov) and/or Open-Meteo** as a fallback and to fill any gaps in what the WU key covers. This matters for a safety app.

**Scope:** personal use, with minimal hosting cost and no auth.

## Open Questions

- **What the WU key covers:** does a weather-station contributor's key include the hourly forecast and the 10-day forecast? If not, Open-Meteo covers 16 days hourly.
- **Nevada road data:** Caltrans doesn't cover the Nevada side. That includes Spooner Summit on US-50, I-80 from Reno to the state line, and SR-88 near Minden. Use NDOT / nvroads 511 for those stretches?
- **Exact route definitions:**
  - US-50 from Reno: via Carson City and Spooner Summit (assumed), or via Mt Rose Hwy, which reaches 8,911 ft?
  - SR-88: from Jackson, continue to Sacramento via SR-16 or SR-49?
- **Forecast points:** where to sample the forecast along each route (summits plus a few midpoints), and how to interpolate between them.
- **Travel-time model:** fixed typical drive times per segment (simplest), or live traffic?
- **Black ice:** we don't have road-surface temperature. Estimate it from air temp, dewpoint, recent precipitation and time of day? Do Caltrans RWIS road sensors offer usable data?
- **Refresh rate and caching:** how often to pull Caltrans (every 5–10 minutes?) and forecasts (hourly?).
- **Tech stack and hosting:** to be decided in planning.

## Next Steps
→ `/workflows:plan` for implementation details
