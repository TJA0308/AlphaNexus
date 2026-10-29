# Deployment

AlphaNexus deploys as two services: the FastAPI backend on Render and the Next.js frontend on Vercel.

## Backend On Render

The repo includes `render.yaml`.

Recommended Render settings:

```text
Service type: Web Service
Runtime: Python
Build command: pip install -r requirements.txt
Start command: uvicorn api.main:app --host 0.0.0.0 --port $PORT
Health check path: /health
```

Set this environment variable after the Vercel frontend URL exists:

```text
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000,http://127.0.0.1:3000
```

Before the Vercel URL exists, keep local origins or temporarily add the expected preview URL.

Render builds from `requirements.txt` with its native Python runtime, not from the `Dockerfile`. The Dockerfile describes the same API as a container (running as an unprivileged user) and is built and health-checked in CI, so it is ready for a host that runs containers.

The default origin list includes the live dashboard at `https://alpha-nexus-ashy.vercel.app`
and localhost. An explicit `ALLOWED_ORIGINS` replaces that list. Add exact preview
URLs to that variable as needed. `ALLOWED_ORIGIN_REGEX` is optional and disabled
by default; use a project-specific expression only if exact URLs are impractical.
Remove any existing `https://.*\.vercel\.app` setting in Render to stop allowing
unrelated Vercel apps. CORS controls browser access; it does not authenticate clients.

## Public API Limits

`POST /backtests` accepts 20 requests per client address in each 60-second window,
including automatic runs with `save=false`. Further requests return HTTP 429 with
a `Retry-After` header and a message the dashboard displays. Health and history
reads remain available. The limiter stores at most 4,096 active client windows;
at capacity, new clients receive 429 until a window expires.

Limits are held in memory and reset on restart. Each worker has its own budget;
the current Render command runs one worker. Before adding workers or replicas,
move enforcement to a shared gateway or store. Clients sharing an IP share a budget.
The limiter uses the ASGI client address and never reads forwarded headers itself.
When deploying behind a proxy, configure Uvicorn to trust forwarded addresses only
from the actual proxy; verify that separate visitors have separate client addresses.

SQLite history retains the newest 1,000 saved runs. Each successful save deletes
older rows in the same transaction. Existing history is trimmed on the next save;
exports already downloaded by users are unaffected.

The project requires yfinance 1.7 or newer. Its downloader uses per-call result state,
so the application only locks its own cache operations, leaving network calls concurrent.
See the [upstream downloader](https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/multi.py).

## Frontend On Vercel

Import the same GitHub repo into Vercel and set the project root to:

```text
frontend
```

Recommended Vercel settings:

```text
Framework preset: Next.js
Build command: npm run build
Install command: npm ci
Output directory: .next
```

Set this environment variable. The frontend also falls back to this Render URL by default, but keeping it explicit in Vercel is clearer:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Then redeploy the frontend.

## Keeping The API Awake

Render's free tier puts the service to sleep after about 15 minutes without traffic, and waking it has taken 40 seconds or more. The dashboard explains the wait after 5 seconds and allows up to 90 seconds before timing out, but the better fix is to avoid the sleep:

1. Create a free monitor at an uptime service such as UptimeRobot.
2. Point an HTTP check at `https://your-render-api.onrender.com/health` every 5 minutes.

One always-on service fits within Render's free monthly hours. The repository's `Keep backend warm` workflow pings the same endpoint on a schedule, but GitHub runs scheduled workflows on a best-effort basis (in practice every few hours), so treat it as a fallback only.

## Deployment Order

1. Deploy Render backend.
2. Copy the Render API URL.
3. Deploy Vercel frontend with `NEXT_PUBLIC_API_BASE_URL`.
4. Copy the Vercel frontend URL.
5. Add the Vercel URL to Render `ALLOWED_ORIGINS`.
6. Redeploy the Render backend.
7. Test a backtest from the Vercel app.

## Smoke Tests

Backend health:

```bash
curl https://your-render-api.onrender.com/health
```

Backtest endpoint:

```bash
curl -X POST https://your-render-api.onrender.com/backtests \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","start":"2024-01-01","end":"2024-12-31","strategy":"sma_crossover","fast_window":17,"slow_window":50}'
```

Frontend proof run:

1. Open the Vercel URL.
2. Keep ticker `AAPL`.
3. Keep strategy `SMA Crossover`.
4. Click `Run Backtest`.
5. Confirm metrics, charts, and trade table render.

## Common Issues

### CORS Error

Add the exact frontend URL to Render:

```text
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
```

Multiple origins must be comma-separated.

For Vercel preview URLs, add the exact URL to `ALLOWED_ORIGINS`, then redeploy
the backend. If you previously enabled the broad Vercel regex, remove it from
Render; changing the repository default does not override an existing environment variable.

### Empty Or Slow Data Response

The app uses `yfinance`, so requests can occasionally fail or slow down because the upstream provider is rate-limited or temporarily unavailable. Retry with a common ticker such as `AAPL` or `MSFT`.

### Frontend Calls Localhost In Production

Set this Vercel environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Then redeploy the frontend.
