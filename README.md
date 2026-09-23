# AlphaNexus

AlphaNexus is a full-stack backtesting workbench for comparing simple, explainable trading rules with buy-and-hold.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Dockerfile-2496ED?logo=docker&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/TJA0308/AlphaNexus/actions/workflows/ci.yml/badge.svg)](https://github.com/TJA0308/AlphaNexus/actions/workflows/ci.yml)

[Live dashboard](https://alpha-nexus-ashy.vercel.app/) | [API documentation](https://alphanexus-api.onrender.com/docs) | [Deployment notes](docs/deployment.md)

![AlphaNexus dashboard showing performance metrics, an equity curve, and drawdown](docs/dashboard.jpeg)

The dashboard runs an example AAPL backtest as soon as it opens. The API runs on Render's free tier; a scheduled workflow keeps it awake, but if it has gone to sleep the first request can take up to ~30s.

## Why I built it

I wanted to understand what happens between a trading idea and the performance number shown at the end of a backtest. A notebook can calculate a return quickly, but it can also hide important details: when a signal becomes tradable, how transaction costs are applied, what happens to cash and shares, and whether the comparison with buy-and-hold is fair.

I built AlphaNexus to make that pipeline inspectable. Market-data loading, indicators, signal generation, portfolio simulation, metrics, API serialization, and frontend rendering live in separate layers. The application is intentionally small enough that I can explain and test each one.

This is a research and education tool, not a trading system or a claim that these strategies generate alpha.

## What it does

- Downloads historical OHLCV data with `yfinance`.
- Runs SMA crossover, RSI mean-reversion, and Bollinger breakout strategies.
- Simulates a long-only portfolio with configurable fees, slippage, and starting capital.
- Compares the strategy with buy-and-hold over the same period.
- Reports return, excess return over buy-and-hold, Sharpe ratio, drawdown, round trips, win rate, and ending equity.
- Displays equity, drawdown, the full trade ledger, and the assumptions behind each run in a Next.js dashboard.
- Stores completed run summaries in SQLite and shows them in a run-history tab.
- Exports the equity curve and trade ledger as CSV.
- Validates input on both sides: the form explains what is wrong before sending, and the API rejects bad requests with a 400 or 422 and upstream data failures with a 502.

## How a backtest moves through the system

```mermaid
flowchart LR
    A[OHLCV data] --> B[Normalize columns]
    B --> C[Calculate indicators]
    C --> D[Generate target position]
    D --> E[Lag signal one bar]
    E --> F[Simulate cash and shares]
    F --> G[Calculate metrics]
    G --> H[FastAPI response]
    H --> I[Next.js dashboard]
```

The analytics code does not depend on the web layer. The engine is a plain Python package, so the tests and the benchmark call it directly without starting a server or a browser.

## Decisions that matter

### Signals execute one bar later

An indicator calculated from bar `t`'s close cannot also trade at that same close. Strategy targets are shifted by one bar before trades are generated, so information observed at `t` is acted on at `t+1`.

This was a correctness issue in an earlier version of the project. Fixing it changed the simulation results, and a regression test now protects the behavior.

### The engine is deliberately long-only

The portfolio holds cash or one long position. That keeps position state, fees, realized PnL, and trade records easy to audit. Short selling, leverage, and multi-asset allocation would require additional margin and risk rules rather than just another UI control.

### The execution loop is sequential, but array-based

Each entry is sized from the cash the previous exit left behind, so the portfolio simulation cannot be a single vectorized expression. It is still a loop, but over NumPy arrays rather than `DataFrame.iterrows()`, which builds a pandas Series for every bar. Output is identical to the old loop; runtime on 50,000 hourly bars dropped from about 8.8 s to about 0.17 s on my machine.

### Annualization counts the bars the provider returns

Sharpe is annualized by bars per year. yfinance returns seven hourly bars per US session (the last covers half an hour), so the hourly factor is `252 × 7`, not the `252 × 6.5` that the session length suggests. I confirmed the count against a month of AAPL and MSFT data.

### Benchmarks use cached data

Network timing and upstream data changes make live downloads unsuitable for regression benchmarks. The benchmark suite therefore uses eight deterministic OHLCV fixtures across three date windows and three strategies: 72 scenarios in total.

### Interfaces are separate from the model

FastAPI validates and serializes requests, while Next.js handles interaction and visualization. The Python package owns the calculations. This separation lets the test suite exercise the engine without starting a browser or web server.

Every endpoint has a Pydantic response model, so the OpenAPI page at `/docs` documents the full contract, and `frontend/lib/types.ts` mirrors it. A test fails if an endpoint is added without a response model.

## Strategies

| Strategy | Entry | Exit |
| --- | --- | --- |
| SMA crossover | Fast SMA rises above slow SMA | Fast SMA falls below slow SMA |
| RSI mean reversion | RSI falls below the oversold threshold | RSI rises above the overbought threshold |
| Bollinger breakout | Close rises above the upper band | Close falls below the center line |

All strategies produce a target position of `1` (long) or `0` (cash). The execution engine turns changes in that target into trades.

## Reproduce the dashboard example

The visible configuration in the screenshot uses:

| Input | Value |
| --- | --- |
| Ticker | `AAPL` |
| Strategy | `SMA Crossover` |
| Interval | `1h` |
| Start | `2025-07-01` |
| End | `2026-07-01` |
| SMA windows | `17 / 61` |
| Starting cash | `$10,000` |
| Fee | `5 bps` |
| Slippage | `5 bps` |

Run the configuration from the live dashboard. The result should render the performance metrics, equity and drawdown charts, executed trades, assumptions, and both CSV downloads. Exact values can change if the upstream provider revises its history.

## Repository layout

```text
alphanexus/
  data.py          Market-data loading and normalization
  indicators.py    SMA, RSI, and Bollinger Bands
  strategies.py    Indicator-to-position rules
  backtest.py      Portfolio and execution simulation
  metrics.py       Risk and performance summaries
  storage.py       SQLite run history
api/main.py        FastAPI routes, request and response models
frontend/
  app/             Next.js page and global styles
  components/      Controls, metrics, charts, tables, run history
  lib/             API client, types, formatting, validation (+ Vitest tests)
benchmarks/        Deterministic fixtures and scenario runner
tests/             Engine, metrics, data, storage, API, and benchmark tests
```

More detail is available in [docs/architecture.md](docs/architecture.md).

## API

```text
GET  /health       Service health
GET  /strategies   Supported strategy metadata
GET  /backtests    Recent run summaries
POST /backtests    Run a backtest and save its summary (?save=false skips saving)
```

Example request:

```bash
curl -X POST https://alphanexus-api.onrender.com/backtests \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "start": "2024-01-01",
    "end": "2024-12-31",
    "interval": "1d",
    "strategy": "sma_crossover",
    "starting_cash": 10000,
    "fee_bps": 5,
    "slippage_bps": 5,
    "allocation": 1,
    "fast_window": 17,
    "slow_window": 50
  }'
```

## Run locally

Python 3.11 or newer and Node.js 22 are recommended.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn api.main:app --reload
```

In a second terminal, point the frontend at the local API (it defaults to the deployed one) and start it:

```bash
cd frontend
echo NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 > .env.local
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:3000` and the API on `http://127.0.0.1:8000`.

To run the API in a container instead:

```bash
docker build -t alphanexus-api .
docker run -p 8000:8000 alphanexus-api
```

## Tests and benchmark

With `make` (macOS, Linux, or WSL), `make check` runs everything CI does except the container check. The individual targets are `lint`, `test`, `coverage`, `benchmark`, and `frontend-check`. Without `make`, run the commands directly:

```bash
ruff check .
pytest --cov
python benchmarks/run_backtest_benchmark.py
```

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

The Python suite covers indicators, signal timing, the execution loop, metrics, data loading and caching, persistence, and the HTTP contract, with market data stubbed out so it never touches the network. Line coverage is about 97%, and CI fails below 90%. The frontend tests cover the API client (including FastAPI's two error shapes), CSV formatting, and form validation.

The deterministic benchmark currently covers:

```text
8 fixtures × 3 date windows × 3 strategies = 72 scenarios
```

CI lints and tests the Python code with coverage (the per-file table appears on each run's summary page), enforces a conservative `100 ms` p95 engine threshold, lints, type-checks, tests and builds the frontend, and verifies the backend container through its health endpoint. Dependabot opens grouped weekly update PRs for the Python and npm dependencies, so CI checks each update before it is merged. Timing numbers vary by machine; the fixture matrix and correctness assertions are the reproducible evidence.

See [benchmarks/README.md](benchmarks/README.md) for the scenario definitions.

## Current boundaries

- Long-only, single-asset portfolios
- End-of-bar signals executed at the following bar's close
- Open positions are valued at the final close rather than forcibly liquidated
- No leverage, short selling, options, or portfolio optimization
- No walk-forward or out-of-sample parameter selection
- No market-impact or order-book model beyond configurable slippage
- Historical data supplied by `yfinance`; hourly bars only reach back about two years
- Prices are split-adjusted but not dividend-adjusted, so neither the strategy nor buy-and-hold earns dividends
- Buy-and-hold is shown without fees or slippage, which makes it a slightly harder benchmark to beat
- SQLite history is ephemeral on hosts without a persistent disk

These boundaries make the application suitable for learning and comparing simple rules. They also mean its results should not be interpreted as evidence that a strategy would perform the same way in live trading.

## Possible next research steps

- Walk-forward evaluation and parameter-sensitivity analysis
- Adjusted-price and corporate-action policy
- Next-open execution and stronger fill assumptions
- Multi-asset portfolio construction
- Comparison against an external benchmark symbol

## License and disclaimer

Released under the [MIT License](LICENSE).

This project is for research and education. It is not financial advice and does not predict future returns.
