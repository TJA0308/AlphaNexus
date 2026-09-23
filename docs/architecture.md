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

The engine is intentionally long-only so the behavior is explainable during interviews.

### Metrics

`alphanexus/metrics.py` summarizes the result:

- total return
- benchmark return
- alpha versus benchmark
- max drawdown
- Sharpe ratio
- trade count
- win rate
- ending equity

### Interfaces

`api/main.py` exposes the engine through FastAPI. It validates requests with Pydantic, maps engine errors to HTTP status codes, and persists run summaries.

`frontend/` contains a Next.js TypeScript interface that calls the FastAPI backend.

## Design Choices

- The core math is outside the UI so it can be tested.
- Strategy configs are dataclasses so parameters are explicit.
- The API uses Pydantic models so requests are validated.
- The dashboard shows the cost assumptions and offers CSV exports, so a result can be checked outside the app.

