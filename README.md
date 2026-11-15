# Pass Check

**Is it safe to drive over the Sierra between Reno and Sacramento, and on which route?**

Pass Check answers that for **I-80 (Donner Summit)**, **US-50 (Spooner + Echo Summit)** and
**SR-88 (Carson Pass)** with a simple **GO / CAUTION / NO GO** for every departure hour over the
next 24 hours, plus a 10-day outlook. It checks each stretch of road at the time you would
actually *reach* it, not just when you leave.

> **Guidance only.** Mountain conditions change fast. Always check
> [Caltrans QuickMap](https://quickmap.dot.ca.gov) before you leave.

## Run it

```bash
curl -O https://raw.githubusercontent.com/treasonx/reno_route_planner/main/compose.yaml
docker compose up -d
open http://localhost:8000
```

Or without compose:

```bash
docker run -d --name pass-check -p 8000:8000 --restart unless-stopped \
  ghcr.io/treasonx/reno_route_planner:latest
```

Images are published for `linux/amd64` and `linux/arm64` (Raspberry Pi, Apple Silicon, ARM NAS).
Tags: `latest` (main), `X.Y.Z` / `X.Y` (releases), `sha-<commit>`.

### Configuration

Everything is optional. With no keys the app uses Caltrans + Open-Meteo.

| Variable | Purpose |
|---|---|
| `WU_API_KEY` | Weather Underground / weather.com key (personal weather station account). Adds a daily snow cross-check at the summits. |
| `NDOT_API_KEY` | Nevada 511 developer key ([nvroads.com/developers/doc](https://www.nvroads.com/developers/doc)). Adds live conditions for the Nevada stretches; without it they are forecast-only and the app says so. |
| `LOG_LEVEL` | Default `INFO`. |

Copy `.env.example` to `.env` next to `compose.yaml` and fill in what you have. `compose.yaml`
lists each variable as `${VAR:-default}`, so Compose fills them from `.env` (or your shell) and
falls back to an empty key (source off) or `INFO`. Keys are never logged or sent to the browser.

### Running it for others

- **Run one worker only.** Data and the refresh schedule live in the process; don't add `--workers`.
- **Restarts.** The last good response from each source is kept in `/data` (the
  `pass-check-data` volume in `compose.yaml`, ~1 MB, no history). After a restart the app serves
  immediately and doesn't refetch until each source's normal interval is up. Restored data is aged
  from when it was originally fetched, so stale data still shows CAUTION, never an old GO.
  Snapshots older than 24 h are ignored. Without a volume it still works; it just warms up for a
  few seconds ("Starting up") after each restart.
- **Fetch schedule.** Open-Meteo once an hour (one request for all points), Weather Underground
  every 3 h, Caltrans and NDOT every 5 min.
- **No authentication.** If you expose it publicly, put it behind a reverse proxy (Caddy,
  Cloudflare Tunnel, `tailscale serve`) that provides TLS, HSTS and per-IP rate limiting, and bind
  the container to `127.0.0.1:8000`.
- **"Add to Home Screen" as an app needs HTTPS** (or `localhost`). Plain `http://LAN-IP:8000`
  works in the browser but won't install.
- **Health:** `GET /api/health` (liveness, used by the image's `HEALTHCHECK`) and
  `GET /api/status` (per-source freshness).

## How the verdict works

Checked per stretch, at the hour you'd reach it (an arrival between hours checks both):

| Verdict | When |
|---|---|
| **NO GO** | Caltrans/NDOT report chain controls (R1–R3) or a closure for arrivals in the next 3 hours, or ≥ ½ in/hr of snow forecast at ≤ 34°F. |
| **CAUTION** | Black ice risk (≤ 34°F overnight/morning after rain, melt or humid air), ≥ 20% chance of snow, light snow, freezing rain, a Caltrans advisory, missing data, or live road data that's delayed. |
| **GO** | None of the above. |

Live road data can only make a verdict worse, never better, and missing or stale data never shows GO.

## Data sources

- [Caltrans CWWP2](https://cwwp2.dot.ca.gov/) chain controls (Districts 3 and 10)
- [Open-Meteo](https://open-meteo.com/) hourly forecast, **CC BY 4.0**. The free API is for
  non-commercial use; see their [terms](https://open-meteo.com/en/terms).
- [Nevada 511](https://www.nvroads.com/) road conditions (optional key)
- Weather Underground / The Weather Company daily forecast (optional key)

## Development

```bash
# backend (Python 3.13, uv)
cd backend && uv sync && uv run pytest
PASSCHECK_SOURCES=fixtures STATIC_DIR=../frontend/dist uv run uvicorn passcheck.main:app_factory --factory --reload

# frontend (Vite + Preact)
cd frontend && npm ci && npm run dev        # proxies /api to :8000
npm run gen:api                             # regenerate types after changing backend schemas
```

`PASSCHECK_SOURCES=fixtures` serves a built-in storm scenario so the UI can be worked on offline.

## Publishing (maintainers)

Pushing to `main` or a `v*` tag builds, scans (Trivy) and pushes the multi-arch image to GHCR
with provenance and an SBOM. GHCR packages start **private**, even for public repos. After the
first push, set it public once: package page → **Package settings** → **Change visibility** →
**Public**. Check with `docker logout ghcr.io && docker pull ghcr.io/treasonx/reno_route_planner:latest`.
