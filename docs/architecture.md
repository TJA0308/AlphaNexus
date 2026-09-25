# Architecture

AlphaNexus is organized around the backtesting workflow instead of around the UI framework. This keeps the project easier to explain and easier to test.

## Data Flow

```text
Market data
  -> data normalization
  -> indicator calculation
  -> strategy signals
  -> portfolio simulation
  -> performance metrics
  -> UI/API response
```

## Layers

### Data

`alphanexus/data.py` downloads market data with `yfinance` and normalizes it into a predictable OHLCV schema:

```text
date, open, high, low, close, volume
```

The rest of the code depends on this schema instead of depending directly on the data provider.

Downloads are cached in memory for 15 minutes (at most 32 windows), and callers receive a copy so one request cannot corrupt the cache for another. A provider failure raises `MarketDataUnavailable` (reported as a 502), while an empty result for a bad ticker or date range raises `ValueError` (a 400).

### Indicators

`alphanexus/indicators.py` contains pure calculation functions:

- Simple moving average
- Bollinger Bands
- Relative Strength Index

These functions accept pandas Series/DataFrames and return computed values. They do not know about the UI or API.

### Strategies

`alphanexus/strategies.py` turns indicators into target positions:

- `1` means the strategy wants to be long.
- `0` means the strategy wants to be in cash.

The module also creates `trade_signal`, which marks position changes.

Targets are shifted by one bar before trades are derived, so a signal computed from bar `t`'s close is acted on at `t+1`. `warmup_bars()` states how many bars each strategy needs before it can hold a position; the engine refuses shorter windows instead of reporting a 0% return that would be indistinguishable from a strategy that chose not to trade.

### Backtest Engine

`alphanexus/backtest.py` simulates the portfolio through time:

- starting cash
- current shares
- trade execution
- fee and slippage assumptions
- realized PnL
- portfolio value
- buy-and-hold benchmark
- drawdown

The engine is long-only by design. Holding either cash or one position keeps position state, fees, and realized PnL auditable trade by trade. Shorting or leverage would need margin, borrow costs, and liquidation rules, which is a different engine rather than an extra option.

### Metrics

`alphanexus/metrics.py` summarizes the result:

- total return
- benchmark return
- excess return versus buy-and-hold (not alpha: there is no beta or risk adjustment)
- max drawdown
- Sharpe ratio
- round trips (completed exits)
- win rate
- ending equity

### Interfaces

`api/main.py` exposes the engine through FastAPI. It validates requests with Pydantic, maps engine errors to HTTP status codes, and persists run summaries to SQLite (`alphanexus/storage.py`, one short-lived connection per call, explicitly closed). `POST /backtests?save=false` runs without saving; the dashboard uses it for the example it loads on first visit so the shared history is not filled with identical runs.

`frontend/` is a Next.js TypeScript dashboard that calls the FastAPI backend:

- `lib/` holds everything that is not rendering: the API client (timeouts, and turning FastAPI's string or list error details into one message), types that mirror the API's response models, formatting, and form validation. These are pure modules with Vitest tests.
- `components/` holds the controls, metric cards, charts, tables, and run history.
- `app/page.tsx` owns state. A result is stored together with the request that produced it, so the badges and assumptions always describe the run on screen, not the form as it is being edited.

## Design Choices

- The core math is outside the UI so it can be tested.
- Strategy configs are dataclasses so parameters are explicit.
- The API uses Pydantic models for requests and responses, so input is validated and the OpenAPI docs describe the full contract.
- Errors are classified by whose fault they are: a bad request is a 400/422, and a market-data provider failure is a 502.
- The dashboard shows the cost assumptions and offers CSV exports, so a result can be checked outside the app.
- The container image runs as an unprivileged user; the only thing it writes is the SQLite file under `/app`.

