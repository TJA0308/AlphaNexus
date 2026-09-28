# AlphaNexus Project Defense

Use this as the interview study sheet. The goal is to understand the system well enough to explain it without memorizing code line by line.

## One-Minute Explanation

AlphaNexus is a full-stack backtesting workbench. A user chooses a ticker, date range, strategy, capital, fees, and slippage. The backend loads OHLCV market data, calculates indicators, converts them into long-only trading signals, simulates a portfolio through time, computes risk/performance metrics, and returns the equity curve and trade ledger to a Next.js dashboard, where the result is compared with buy-and-hold.

The part I focused on is correctness: signals trade one bar after they are observed (no look-ahead), too-short windows are refused instead of reported as a 0% return, and every fix has a test that fails on the old code.

## Data Flow

```text
OHLCV data (yfinance, cached 15 min)
  -> normalized price DataFrame
  -> indicators
  -> target position (signal), lagged one bar
  -> trade signal (+1 buy, -1 sell)
  -> portfolio simulation (cash, shares, fees, slippage)
  -> metrics
  -> API response (+ saved to SQLite)
  -> dashboard charts/tables/exports
```

## Core Modules

| File | Responsibility |
| --- | --- |
| `alphanexus/data.py` | Downloads, normalizes, and caches OHLCV data from `yfinance` |
| `alphanexus/indicators.py` | Computes SMA, RSI (Wilder smoothing), and Bollinger Bands |
| `alphanexus/strategies.py` | Converts indicators into target positions, lags them one bar, and derives trade signals; `warmup_bars()` states the minimum data each strategy needs |
| `alphanexus/backtest.py` | Simulates cash, shares, fees, slippage, realized PnL, equity, drawdown, and the buy-and-hold benchmark |
| `alphanexus/metrics.py` | Computes return, excess return vs buy-and-hold, drawdown, Sharpe, win rate, and round trips |
| `alphanexus/storage.py` | Saves run summaries to SQLite (one connection per call, explicitly closed) |
| `api/main.py` | Validates requests and responses with Pydantic and exposes the FastAPI endpoints |
| `frontend/app/page.tsx` | Dashboard page: holds state and wires the pieces together |
| `frontend/components/` | Controls, metric cards, charts, tables, run history |
| `frontend/lib/` | API client, types, formatting, validation (unit-tested with Vitest) |
| `benchmarks/` | Runs deterministic scenario benchmarks on cached fixtures |

## Strategy Logic

SMA crossover:
The strategy is long when the fast moving average is above the slow moving average. It exits when the fast average falls below the slow average.

RSI mean reversion:
The strategy buys when RSI falls below an oversold threshold and exits when RSI rises above an overbought threshold. Between the two, it keeps its last decision (forward-filled).

Bollinger breakout:
The strategy buys when price closes above the upper band and exits when price falls below the center line.

## The Two Correctness Decisions

**Signals execute one bar later (no look-ahead bias).**
An indicator computed from bar `t`'s close cannot trade at that same close, because the close is only known once the bar is over. The target position is shifted one bar (`signal.shift(1)`), so information seen at `t` is acted on at `t+1`. An earlier version got this wrong, which made results look better than reality; a regression test now guards it.

**Too-short windows are refused, not reported as 0%.**
Each indicator needs a full window before it produces a value (for example, 50 bars for a 50-bar SMA, plus 1 for the lag). With less data the signal stays 0 and the old code reported "0.00% return, 0 trades", which looks like a strategy that was tested and chose not to trade. The output alone cannot tell the difference, because a flat market also produces an all-zero signal. So `warmup_bars()` computes the requirement from the window lengths, and the engine returns a 400 that says how many bars were available and how many are needed.

## Backtest Logic

The engine is long-only. It holds either cash or one long position.

On a buy signal, it spends `cash × allocation`, splits that into position and fee (`position = spent / (1 + fee_rate)`), fills at the close plus slippage, and records the shares bought. A 100% allocation leaves exactly 0 cash.

On a sell signal, it fills at the close minus slippage, deducts the fee from the proceeds, records realized PnL, and returns to cash.

Every bar, portfolio value = cash + shares × close (marked to market). A position still open at the end is valued at the final close but not counted as a completed trade.

It is a loop because each entry is sized from the cash the previous exit left. It loops over NumPy arrays rather than `iterrows()`: identical output, 50,000 bars in ~0.17 s instead of ~8.8 s.

## Metrics

| Metric | Meaning |
| --- | --- |
| Total return | Strategy ending equity divided by starting equity minus 1 |
| Buy & hold return | Same calculation for buying at the first close and holding (no costs) |
| Excess return vs benchmark | Strategy return minus buy-and-hold return. Not alpha: no beta or risk adjustment |
| Max drawdown | Largest peak-to-trough portfolio decline |
| Sharpe ratio | Mean per-bar return over its standard deviation, times the square root of bars per year (252 daily, 252 × 7 hourly) |
| Round trips | Number of completed exits (one buy + one sell counts once) |
| Win rate | Fraction of exits with positive realized PnL |
| Ending equity | Final portfolio value |

## Errors

| Status | When |
| --- | --- |
| 422 | The request does not match the schema (wrong type, out-of-range value, unknown strategy) |
| 400 | An engine rule fails (fast SMA not shorter than slow, window too short) or the ticker/date range returns no data |
| 502 | The market-data provider is down or rate-limiting: nothing the caller sent was wrong |

## Benchmark Methodology

The benchmark uses `8` cached synthetic OHLCV fixtures, `3` date windows, and `3` strategies for `72` total scenarios.

It measures only the Python simulation path:

```text
load cached fixture
  -> run strategy
  -> run portfolio simulation
  -> compute metrics
```

It does not measure live API downloads, frontend rendering, Render cold starts, or network latency. That makes the result stable enough to defend as an engine benchmark. CI fails if the p95 run time goes over 100 ms; locally it is about 11–15 ms.

## Resume Bullets

Built a full-stack backtesting platform (Python/pandas engine, FastAPI, Next.js/TypeScript, Docker) deployed on Render and Vercel, with CI running 98 Python tests (~97% coverage), 32 frontend tests, and a 72-scenario performance benchmark on every pull request.

Found and fixed a look-ahead bias that let simulated trades use the same bar's closing price, and made the engine refuse data windows too short for a strategy to warm up instead of reporting a misleading 0% return; both are guarded by regression tests.

Cut backtest runtime ~50× at 50,000 bars (8.8 s to 0.17 s) by replacing row-by-row `iterrows()` with a NumPy-array execution loop, verified to produce identical output.

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

Why is the execution loop still a loop?
Each entry is sized from the cash the previous exit left, so bar t depends on every trade before it. What made it slow was `iterrows()`, which builds a pandas Series per bar. Looping over NumPy arrays kept the logic identical and made 50,000 bars run in ~0.17 s instead of ~8.8 s. Most of the remaining time on small inputs is fixed pandas overhead, not the loop.

What was wrong with the drawdown chart?
Recharts only renders an `<Area>` inside an `AreaChart` or `ComposedChart`. It was inside a `LineChart`, which drew the axes and silently dropped the series. There was no error, which is why it shipped.

What would you improve next?
Walk-forward testing (tune parameters on one window, evaluate on the next) and a parameter-sensitivity view, since a single backtest invites overfitting. After that, next-open execution and dividend-adjusted prices.
