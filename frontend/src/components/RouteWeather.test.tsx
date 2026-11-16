import { cleanup, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it } from "vitest";

import plan from "../__fixtures__/plan.json";
import type { PlanResponse, RouteOut } from "../types";
import { RouteWeather } from "./RouteWeather";

const fixture = plan as PlanResponse;
const hour = fixture.hours[0]!;

afterEach(cleanup);

const renderTile = (route: RouteOut, key: "i80" | "us50" = "i80", stale = false) =>
  render(
    <RouteWeather corridor={fixture.corridors[key]} route={route} depart={hour.depart} leaving="now" stale={stale} />,
  );

describe("RouteWeather", () => {
  it("lists every stop in driving order with the time you pass it", () => {
    renderTile(hour.routes.i80);
    expect(screen.getByRole("heading", { name: "Weather on I-80" })).toBeTruthy();
    const items = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(items).toHaveLength(fixture.corridors.i80.stops.length + 1); // + freezing level
    expect(items[0]).toMatch(/^Reno, 7:00 AM: \d+°F/);
    expect(items[2]).toMatch(/^Donner Summit, 7:50 AM/);
  });

  it("shows '–' for a stop with no forecast and keeps 0″ for no snow", () => {
    const route: RouteOut = {
      ...hour.routes.i80,
      weather: hour.routes.i80.weather.map((w, i) =>
        i === 0 ? { ...w, temp_f: null, snow_depth_in: null, snowfall_in_hr: null } : { ...w, snow_depth_in: i === 2 ? 18 : 0 },
      ),
    };
    const { container } = renderTile(route);
    const temps = [...container.querySelectorAll(".wx-temp")].map((e) => e.textContent);
    expect(temps[0]).toBe("–");
    const depths = [...container.querySelectorAll(".wx-depth")].map((e) => e.textContent);
    expect(depths[0]).toBe("–");
    expect(depths[1]).toBe("0″");
    expect(depths[2]).toBe("18″");
  });

  it("collapses the snow lane when there is no snow anywhere", () => {
    const route: RouteOut = {
      ...hour.routes.i80,
      weather: hour.routes.i80.weather.map((w) => ({ ...w, snow_depth_in: 0, snowfall_in_hr: 0 })),
    };
    const { container } = renderTile(route);
    expect(container.querySelector(".wx-nosnow")?.textContent).toBe("No snow on the ground or falling");
    expect(container.querySelector(".wx-snow")).toBeNull();
  });

  it("staggers names for 7+ stops and dims when stale", () => {
    const { container, unmount } = renderTile(hour.routes.i80);
    expect(container.querySelector(".wx-names.stagger")).not.toBeNull();
    unmount();
    const us50 = renderTile(hour.routes.us50, "us50", true);
    expect(us50.container.querySelector(".wx-names.stagger")).not.toBeNull();
    expect(us50.container.querySelector(".route-weather.is-stale")).not.toBeNull();
  });

  it("draws the freezing line inside the profile and tells screen readers", () => {
    const { container } = renderTile({ ...hour.routes.i80, freezing_level_ft: 5500 });
    expect(container.querySelector(".wx-freeze")).not.toBeNull();
    expect(container.querySelector(".wx-freeze-key")?.textContent).toBe("32°F at 5,500′ at summit");
    expect(screen.getByText("Freezing level over the summit: 5,500 feet")).toBeTruthy();
  });

  it("hides the freezing line when the freezing level is above the summit", () => {
    const { container } = renderTile({ ...hour.routes.i80, freezing_level_ft: 328084 });
    expect(container.querySelector(".wx-freeze")).toBeNull();
    expect(container.querySelector(".wx-freeze-key")).toBeNull();
  });
});
