# AlphaNexus Project Defense

Use this as the interview study sheet. The goal is to understand the system well enough to explain it without memorizing code line by line.

## One-Minute Explanation

AlphaNexus is a full-stack quantitative research workbench. A user chooses a ticker, date range, strategy, capital, fees, and slippage. The backend loads OHLCV market data, calculates indicators, converts them into long-only trading signals, simulates a portfolio through time, computes risk/performance metrics, and returns the equity curve and trade ledger to a Next.js dashboard.

I added a deterministic benchmark suite because live market-data timing is noisy. The benchmark runs a fixed matrix of cached fixture scenarios so I can measure engine reliability and runtime in a reproducible way.

## Data Flow

```text
OHLCV data
  -> normalized price DataFrame
  -> indicators
  -> strategy signal
  -> trade signal
  -> portfolio simulation
  -> metrics
  -> API response
  -> dashboard charts/tables/exports
```

## Core Modules

| File | Responsibility |
| --- | --- |
| `alphanexus/data.py` | Downloads and normalizes OHLCV data from `yfinance` |
| `alphanexus/indicators.py` | Computes SMA, RSI, and Bollinger Bands |
| `alphanexus/strategies.py` | Converts indicators into target positions and trade signals |
| `alphanexus/backtest.py` | Simulates cash, shares, fees, slippage, PnL, equity, and benchmark |
| `alphanexus/metrics.py` | Computes return, alpha, drawdown, Sharpe, win rate, and trade count |
| `api/main.py` | Validates requests and exposes the FastAPI endpoints |
| `frontend/app/page.tsx` | Provides the interactive Next.js dashboard |
| `benchmarks/` | Runs deterministic scenario benchmarks on cached fixtures |

## Strategy Logic

SMA crossover:
The strategy is long when the fast moving average is above the slow moving average. It exits when the fast average falls below the slow average.

RSI mean reversion:
The strategy buys when RSI falls below an oversold threshold and exits when RSI rises above an overbought threshold.

Bollinger breakout:
The strategy buys when price closes above the upper band and exits when price falls below the center line.

## Backtest Logic

The engine is long-only. It holds either cash or one long position.

On a buy signal, it uses the configured allocation of cash, applies slippage to the entry price, deducts fees, and records the shares purchased.

On a sell signal, it exits the position, applies slippage to the sale price, deducts fees, calculates realized PnL, and returns to cash.

After every row, the engine records portfolio value, strategy return, benchmark value, benchmark return, and drawdown.

## Metrics

| Metric | Meaning |
| --- | --- |
| Total return | Strategy ending equity divided by starting equity minus 1 |
| Benchmark return | Buy-and-hold return over the same period |
| Alpha vs benchmark | Strategy return minus benchmark return |
| Max drawdown | Largest peak-to-trough portfolio decline |
| Sharpe ratio | Average excess return divided by volatility, annualized |
| Trade count | Number of completed exits |
| Win rate | Fraction of profitable exits |
| Ending equity | Final portfolio value |

## Benchmark Methodology

The benchmark uses `8` cached synthetic OHLCV fixtures, `3` date windows, and `3` strategies for `72` total scenarios.

It measures only the Python simulation path:

```text
load cached fixture
  -> run strategy
  -> run portfolio simulation
  -> compute metrics
```

It does not measure live API downloads, frontend rendering, Render cold starts, or network latency. That makes the result stable enough to defend as an engine benchmark.

Example local result:

```text
72/72 scenarios passed
100.0% pass rate
24,120 fixture rows processed
13.71 ms median engine runtime
20.85 ms p95 engine runtime
```

## Resume-Ready XYZ Bullets

Built a full-stack backtesting platform that validates `72` reproducible strategy scenarios with `100%` pass rate and `sub-30 ms` p95 engine runtime locally, by creating cached OHLCV fixtures, a benchmark scenario matrix, and regression tests around a Python/FastAPI analytics engine.

Engineered an explainable quantitative research dashboard supporting `3` strategies, `2` market-data intervals, and `8` risk/performance metrics, by separating market-data normalization, indicator calculation, signal generation, portfolio simulation, API validation, and Next.js visualization into modular layers.

Improved backtest defensibility by exposing fees, slippage, trade-level PnL, benchmark comparison, drawdown, assumptions, and CSV exports, by building a typed FastAPI contract and interactive Next.js/Streamlit interfaces for repeatable strategy analysis.

## Common Interview Questions

What problem does this solve?
It turns a trading idea into a repeatable research workflow. Instead of manually testing logic in a notebook, the user can configure a strategy, run a simulation, inspect assumptions, compare against buy-and-hold, and export evidence.

Why not call it a trading bot?
It does not place trades or make predictions. It is a research and education tool for historical strategy evaluation.

Why use cached synthetic data for benchmarks?
Because live data downloads introduce network and provider noise. Synthetic fixtures let me measure my engine consistently across known market regimes.

What is the difference between signal and trade signal?
`signal` is the desired target state, such as long or cash. `trade_signal` is the change in state, such as buy or sell.

Where do fees and slippage enter?
They are applied only when trades execute. Buy trades increase the execution price and deduct fees. Sell trades decrease the execution price and deduct fees from proceeds.

What is the benchmark?
The benchmark is buy-and-hold over the same selected period, using the same starting capital.

What would you improve next?
I would add persisted run history with SQLite or DuckDB, walk-forward testing, and end-to-end browser tests for the deployed dashboard.
