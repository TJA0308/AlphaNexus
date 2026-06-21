# Deployment

AlphaNexus has two deployable surfaces:

1. Streamlit demo: fastest public demo path.
2. FastAPI + Next.js: full-stack version for a stronger engineering showcase.

## Option 1: Streamlit Community Cloud

Use this for the first public demo.

```text
Repository: TJA0308/AlphaNexus
Branch: main
Main file path: app.py
```

Streamlit installs dependencies from `requirements.txt`.

After deployment:

1. Open the app.
2. Click `Load demo preset`.
3. Click `Run backtest`.
4. Verify the Performance, Trades, Assumptions, and Exports tabs.
5. Add the live URL to the README.

## Option 2: Render API + Vercel Frontend

Use this for the full-stack version.

### Backend On Render

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

### Frontend On Vercel

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

Set this environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Then redeploy the frontend.

### Deployment Order

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

### Empty Or Slow Data Response

The app uses `yfinance`, so requests can occasionally fail or slow down because the upstream provider is rate-limited or temporarily unavailable. Retry with a common ticker such as `AAPL` or `MSFT`.

### Frontend Calls Localhost In Production

Set this Vercel environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Then redeploy the frontend.
