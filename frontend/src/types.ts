import type { components } from "./api.gen";

type Schemas = components["schemas"];

export type PlanResponse = Schemas["PlanResponse"];
export type HourOut = Schemas["HourOut"];
export type DayOut = Schemas["DayOut"];
export type RouteOut = Schemas["RouteOut"];
export type CorridorOut = Schemas["CorridorOut"];
export type StopOut = Schemas["StopOut"];
export type StopWeatherOut = Schemas["StopWeatherOut"];
export type VerdictLevel = RouteOut["verdict"];
export type RouteKey = Schemas["BestOut"]["route"];
export type Direction = PlanResponse["direction"];

export const ROUTE_KEYS: readonly RouteKey[] = ["i80", "us50", "sr88"];
