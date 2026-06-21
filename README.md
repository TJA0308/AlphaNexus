# AlphaNexus Backtesting Lab

[![CI](https://github.com/TJA0308/AlphaNexus/actions/workflows/ci.yml/badge.svg)](https://github.com/TJA0308/AlphaNexus/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-000000)
![Streamlit](https://img.shields.io/badge/Streamlit-Demo-FF4B4B)

AlphaNexus is a backtesting workbench for testing simple long-only trading rules on historical market data. It compares a strategy against buy-and-hold, applies fee and slippage assumptions, and reports risk and trade-level results.

The project is intentionally explainable: the strategies are simple, but the codebase is split into data loading, indicators, signal generation, portfolio simulation, metrics, API responses, and UI rendering.

## Demo

The Streamlit app is the recommended public demo because it runs from a single entry point.

```text
Main file path: app.py
```

Streamlit Community Cloud settings:

```text
Repository: TJA0308/AlphaNexus
Branch: main
Main file path: app.py
```

After deployment, add the live URL here:

```text
Live demo: pending
```

## Features

- Load historical OHLCV data with `yfinance`
- Run SMA crossover, RSI mean reversion, and Bollinger breakout strategies
- Simulate a long-only portfolio with cash, shares, fees, and slippage
- Compare strategy performance against buy-and-hold
- Calculate total return, benchmark return, max drawdown, Sharpe ratio, win rate, and trade count
- Inspect executed trades and realized PnL
- Export trade ledger, equity curve, summary metrics, and recent run history as CSV
- Use either a Streamlit demo UI or a FastAPI + Next.js full-stack path
- Use Radix UI primitives and Recharts in the Next.js dashboard
- Run automated Python tests and frontend builds through GitHub Actions

## Tech Stack

| Layer | Tools |
| --- | --- |
| Analytics | Python, pandas, NumPy |
| Data | yfinance |
| API | FastAPI, Pydantic |
| Demo UI | Streamlit, Plotly |
| Frontend scaffold | Next.js, TypeScript, Radix UI, Recharts |
| Testing | pytest, GitHub Actions |

## Architecture

```text
Market data
  -> normalization
  -> indicators
  -> strategy signals
  -> portfolio simulation
  -> metrics
  -> Streamlit UI / FastAPI response
```

Project layout:

```text
.
|-- alphanexus/
|   |-- backtest.py       # Portfolio simulation engine
|   |-- data.py           # Market data loading and normalization
|   |-- indicators.py     # SMA, RSI, Bollinger Bands
|   |-- metrics.py        # Sharpe, drawdown, performance summary
|   `-- strategies.py     # Strategy signal generation
|-- api/
|   `-- main.py           # FastAPI app
|-- frontend/
|   `-- app/              # Next.js TypeScript interface
|-- tests/                # pytest coverage for core logic
|-- docs/
|   `-- architecture.md   # Detailed design notes
|-- app.py                # Streamlit demo interface
|-- requirements.txt
`-- pyproject.toml
```

More detail: [docs/architecture.md](docs/architecture.md)

Deployment guide: [docs/deployment.md](docs/deployment.md)

## How The Backtest Works

1. Load historical OHLCV data for a ticker.
2. Calculate indicators such as moving averages, RSI, or Bollinger Bands.
3. Convert indicators into long-only target positions.
4. Execute position changes while tracking cash, shares, fees, and slippage.
5. Build a strategy equity curve and buy-and-hold benchmark.
6. Report risk metrics and trade-level realized PnL.

## Assumptions

- Long-only portfolio: the simulator holds cash or one long position.
- Signals are generated from historical close prices.
- Fees and slippage are applied on executed trades.
- The benchmark is buy-and-hold over the same selected period.
- Results are for research and education, not financial advice.
- Historical data may change if the provider revises records.

## Local Setup

Create a virtual environment and install Python dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the Streamlit demo:

```bash
streamlit run app.py
```

Run the FastAPI backend:

```bash
uvicorn api.main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Run the Next.js frontend:

```bash
cd frontend
cmd /c npm install
cmd /c npm run dev
```

The frontend expects the API at:

```text
http://127.0.0.1:8000
```

For full-stack deployment, see [docs/deployment.md](docs/deployment.md).

## API Example

```bash
curl -X POST http://127.0.0.1:8000/backtests ^
  -H "Content-Type: application/json" ^
  -d "{\"ticker\":\"AAPL\",\"start\":\"2024-01-01\",\"end\":\"2024-12-31\",\"strategy\":\"sma_crossover\"}"
```

Main endpoints:

```text
GET  /health
GET  /strategies
POST /backtests
```

## Testing

Run the Python test suite:

```bash
pytest
```

Build the frontend:

```bash
cmd /c npm --prefix frontend run build
```

CI runs both checks on pushes and pull requests to `main`.

## What I Learned

- How to separate analytics logic from UI code
- Why backtests need explicit assumptions around fees, slippage, and execution timing
- How benchmark comparison changes the interpretation of raw returns
- How to expose the same analytics engine through both Streamlit and FastAPI
- How to add tests around financial calculations instead of only testing UI behavior

## Interview Explanation

> I built a backtesting dashboard to learn how analytics products are structured end to end. The backend fetches market data, computes indicators, generates trading signals, simulates a portfolio with fees and slippage, and returns risk metrics. The app lets a user configure a strategy and inspect the equity curve, drawdown, benchmark comparison, trade ledger, and exported results.

## Resume Bullet

> Built a full-stack financial backtesting dashboard using Python, FastAPI, pandas, NumPy, Next.js, TypeScript, and Streamlit, enabling users to test parameterized trading strategies, compare against buy-and-hold benchmarks, and analyze Sharpe ratio, max drawdown, win rate, and trade-level PnL.

## Roadmap

- Add screenshots and the live Streamlit URL after deployment
- Add saved backtest history with SQLite or DuckDB
- Add walk-forward testing to reduce overfitting
- Add portfolio-level multi-asset allocation
- Add Playwright tests for the Next.js user flow
- Add Dockerfiles for consistent deployment

## Disclaimer

This project is a research and education tool. It is not financial advice, and it does not predict future returns.
