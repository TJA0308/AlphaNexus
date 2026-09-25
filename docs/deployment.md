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

The backend also supports Vercel preview and production deployments through:

```text
ALLOWED_ORIGIN_REGEX=https://.*\.vercel\.app
```

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

For Vercel preview URLs, keep this regex enabled in Render:

```text
ALLOWED_ORIGIN_REGEX=https://.*\.vercel\.app
```

### Empty Or Slow Data Response

The app uses `yfinance`, so requests can occasionally fail or slow down because the upstream provider is rate-limited or temporarily unavailable. Retry with a common ticker such as `AAPL` or `MSFT`.

### Frontend Calls Localhost In Production

Set this Vercel environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Then redeploy the frontend.
