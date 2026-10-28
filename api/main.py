from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.data import TICKER_PATTERN, MarketDataUnavailable, fetch_prices
from alphanexus.storage import recent_runs, save_run
from alphanexus.strategies import StrategyConfig, StrategyName
from alphanexus.validation import MAX_COST_BPS, MAX_STARTING_CASH, MAX_WINDOW
from api.limits import BacktestLimiter

logger = logging.getLogger(__name__)


def allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://alpha-nexus-ashy.vercel.app",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def allowed_origin_regex() -> str | None:
    return os.getenv("ALLOWED_ORIGIN_REGEX") or None


class BacktestRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    ticker: str = Field(default="AAPL", min_length=1, max_length=20, pattern=TICKER_PATTERN)
    start: date
    end: date
    interval: Literal["1d", "1h"] = "1d"
    strategy: StrategyName = "sma_crossover"
    starting_cash: float = Field(default=10_000, gt=0, le=MAX_STARTING_CASH)
    fee_bps: float = Field(default=5, ge=0, le=MAX_COST_BPS)
    slippage_bps: float = Field(default=5, ge=0, le=MAX_COST_BPS)
    allocation: float = Field(default=1, gt=0, le=1)
    fast_window: int = Field(default=20, gt=1, le=MAX_WINDOW)
    slow_window: int = Field(default=50, gt=2, le=MAX_WINDOW)
    rsi_window: int = Field(default=14, gt=1, le=MAX_WINDOW)
    oversold: float = Field(default=30, gt=0, lt=100)
    overbought: float = Field(default=70, gt=0, lt=100)
    band_window: int = Field(default=20, gt=1, le=MAX_WINDOW)
    band_std: float = Field(default=2, gt=0, le=100)


class Metrics(BaseModel):
    total_return: float
    benchmark_return: float
    excess_return_vs_benchmark: float
    max_drawdown: float
    sharpe_ratio: float
    trade_count: int
    win_rate: float
    ending_equity: float


class EquityPoint(BaseModel):
    date: datetime
    close: float
    portfolio_value: float
    benchmark_value: float
    drawdown: float
    signal: int
    trade_signal: int


class Trade(BaseModel):
    date: datetime
    signal_date: datetime
    close: float
    fill_price: float
    fee: float
    cash_before: float
    trade_signal: int
    shares: float
    cash: float
    portfolio_value: float
    realized_pnl: float


class BacktestResponse(BaseModel):
    ticker: str
    strategy: StrategyName
    metrics: Metrics
    equity_curve: list[EquityPoint]
    trades: list[Trade]


class StrategyInfo(BaseModel):
    id: StrategyName
    name: str


class RunSummary(BaseModel):
    id: int
    created_at: str
    ticker: str
    strategy: str
    start_date: date
    end_date: date
    interval: str
    total_return: float
    benchmark_return: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int


app = FastAPI(
    title="AlphaNexus Backtesting API",
    version="1.0.1",
    description="Backtest simple trading strategies and return risk/performance analytics.",
)
app.state.backtest_limiter = BacktestLimiter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_origin_regex=allowed_origin_regex(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies", response_model=list[StrategyInfo])
def list_strategies() -> list[dict[str, str]]:
    return [
        {"id": "sma_crossover", "name": "SMA Crossover"},
        {"id": "rsi_mean_reversion", "name": "RSI Mean Reversion"},
        {"id": "bollinger_breakout", "name": "Bollinger Breakout"},
    ]


@app.get("/backtests", response_model=list[RunSummary])
def list_backtests(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    # The bounds are load-bearing, not decoration: SQLite treats a negative
    # LIMIT as "no limit", so an unvalidated ?limit=-1 would return the entire
    # runs table in one response.
    return recent_runs(limit)


@app.post("/backtests", response_model=BacktestResponse)
def create_backtest(
    request: BacktestRequest,
    http_request: Request,
    save: bool = Query(
        default=True,
        description="Record the run in the history. The dashboard's automatic first-load run passes false.",
    ),
) -> BacktestResponse:
    # Use the ASGI peer address. Forwarded headers belong to the server's
    # trusted-proxy configuration, never to an arbitrary caller's header.
    client = http_request.client.host if http_request.client else "unknown"
    retry_after = http_request.app.state.backtest_limiter.retry_after(client)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail=f"Too many backtests. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    if request.start >= request.end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        strategy_config = StrategyConfig(
            name=request.strategy,
            fast_window=request.fast_window,
            slow_window=request.slow_window,
            rsi_window=request.rsi_window,
            oversold=request.oversold,
            overbought=request.overbought,
            band_window=request.band_window,
            band_std=request.band_std,
        )
        backtest_config = BacktestConfig(
            starting_cash=request.starting_cash,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            allocation=request.allocation,
            interval=request.interval,
        )
        strategy_config.validate()
        backtest_config.validate()
        prices = fetch_prices(request.ticker.upper(), request.start, request.end, request.interval)
        result, metrics = run_backtest(prices, strategy_config, backtest_config)
    except MarketDataUnavailable as exc:
        # The upstream provider is down or rate-limiting us. Nothing the caller
        # sent is wrong, so this is a gateway failure, not a bad request.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Persist a summary of the run so it shows up in the history endpoint.
    # The dashboard runs a default backtest for every visitor on first load;
    # saving those would bury real runs under identical copies.
    if save:
        try:
            save_run(
                ticker=request.ticker.upper(),
                strategy=request.strategy,
                start_date=str(request.start),
                end_date=str(request.end),
                interval=request.interval,
                metrics=metrics,
            )
        except sqlite3.Error:
            # History is a convenience; a locked or read-only database should
            # not throw away a backtest that already succeeded.
            logger.exception("could not save backtest run to history")

    equity_columns = [
        "date",
        "close",
        "portfolio_value",
        "benchmark_value",
        "drawdown",
        "signal",
        "trade_signal",
    ]
    trades = result[result["trade_signal"] != 0][
        [
            "date", "signal_date", "close", "fill_price", "fee", "cash_before",
            "trade_signal", "trade_shares", "cash", "portfolio_value", "realized_pnl",
        ]
    ].rename(columns={"trade_shares": "shares"})

    return BacktestResponse(
        ticker=request.ticker.upper(),
        strategy=request.strategy,
        metrics=metrics,
        equity_curve=result[equity_columns].to_dict(orient="records"),
        trades=trades.to_dict(orient="records"),
    )
