# Correctness and execution audit update

Implemented locally on 2026-10-28. Deployment is separate.

## Behavior changes

The engine and API reject invalid cost/capital configurations. Fees and slippage
are each bounded to 0–1,000 basis points per execution; starting cash must be
finite, positive and no more than $1 trillion. Active strategy windows must be
integers from 2 through 10,000, with fast SMA strictly below slow SMA. Invalid
strategy relationships are checked before downloading data.

The new `alphanexus/validation.py` validates data before signal generation:
valid unique timestamps with a consistent timezone, numeric finite positive
prices, nonnegative volume, and consistent OHLC when all those columns exist.
Direct engine callers can still supply date/close only. Inputs are copied and
sorted without mutating the caller. Missing/invalid observations are rejected,
not removed or imputed. Non-finite portfolio outputs cannot be returned as a
successful backtest.

RSI now uses an arithmetic-mean seed over the first window of changes followed
by Wilder's recurrence. For closes `[10, 11, 10, 12, 11, 13]` and window 3, the
first three defined values are `75, 54.54545..., 75`. Earlier output stays
undefined. Existing RSI results can change; this is an intentional numerical
correction, not a performance optimization.

An empty yfinance download now returns a 502 with an explanation that the
cause is ambiguous. The downloader can hide provider exceptions in empty
frames. Malformed provider data also returns 502 and is not cached. This
does not yet identify a structured "unknown symbol" versus "no sessions"
cause; it avoids asserting a cause the adapter cannot establish.

## Execution contract

Each returned trade contains:

| Field | Meaning |
| --- | --- |
| `signal_date` | Earlier bar whose closing data produced the decision |
| `date` | Execution bar; fills still occur at this bar's close |
| `close` | Reference closing price before slippage |
| `fill_price` | Actual simulated execution price after slippage |
| `fee` | Cash commission charged on that execution |
| `shares` | Quantity bought or sold |
| `cash_before` | Available cash before the execution |
| `cash` | Available cash after the execution |
| `realized_pnl` | Net exit proceeds minus the entry cost, including fees |

For a buy: `cash = cash_before - shares * fill_price - fee`.
For a sell: `cash = cash_before + shares * fill_price - fee`.
Use a small floating-point tolerance when checking equality. Portfolio value
marks shares at the reference close, so it need not equal cash plus shares
times the execution price. Open positions are not force-liquidated.

The UI separately displays reference closes, fills, fees, quantities and cash
balances. The CSV retains numeric precision and signal timestamps. The
Assumptions tab now also shows strategy-specific settings for the displayed run.

## Verification

Local checks completed: 174 Python tests, 97.55% line coverage, 47 frontend
unit tests, 26 desktop/mobile browser tests, Python/frontend lint, TypeScript
checking and production frontend build. The 72-scenario benchmark passed with
p95 engine runtime 12.94 ms on this machine. Browser tests use mocked API
responses and do not establish live deployment integration.

Regression tests include independent Wilder arithmetic, cost limits and
non-finite inputs, malformed dates/prices/OHLC, data-copy behavior, early API
rejection, and cash/PnL reconciliation for zero, typical and maximum supported
costs. Browser fixtures are regenerated through the actual API/engine. Browser
tests inspect the ledger fields and reconcile an exported CSV entry.

Run `python -m pytest --cov`, `python -m ruff check .`, the deterministic
benchmark, frontend unit/lint/type/build checks, and Playwright before release.
Installed dependencies may differ from declared requirements; fresh locked
environment verification remains separate work.

## Deployment and compatibility

Deploy backend before frontend: ledger fields are additive to the response,
so the previous frontend can consume the updated API, but the updated frontend
expects the new fields. The live deployment has not been changed by this work.
For local work set `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`; otherwise
the dashboard defaults to the deployed API.

## Remaining roadmap

This is the first implementation increment, not completion of the entire
review. Remaining work includes exchange/currency metadata enforcement,
session completeness and partial-bar policies, complete persistent experiments
and replay, truthful save-status reporting, durable storage, research comparison
and holdout evaluation, and a real browser-to-API integration test. The API still
accepts generic ticker syntax; the UI explicitly states its US-equity/USD
model assumptions. The current data validator does not establish asset scope.
