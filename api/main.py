from __future__ import annotations

from datetime import date
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.data import fetch_prices
from alphanexus.strategies import StrategyConfig, StrategyName


def allowed_origins() -> list[str]:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


class BacktestRequest(BaseModel):
    ticker: str = Field(default="AAPL", min_length=1, max_length=20)
    start: date
    end: date
    interval: Literal["1d", "1h"] = "1d"
    strategy: StrategyName = "sma_crossover"
    starting_cash: float = Field(default=10_000, gt=0)
    fee_bps: float = Field(default=5, ge=0)
    slippage_bps: float = Field(default=5, ge=0)
    allocation: float = Field(default=1, gt=0, le=1)
    fast_window: int = Field(default=20, gt=1)
    slow_window: int = Field(default=50, gt=2)
    rsi_window: int = Field(default=14, gt=1)
    oversold: float = Field(default=30, gt=0, lt=100)
    overbought: float = Field(default=70, gt=0, lt=100)
    band_window: int = Field(default=20, gt=1)
    band_std: float = Field(default=2, gt=0)


class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    metrics: dict[str, float | int]
    equity_curve: list[dict]
    trades: list[dict]


app = FastAPI(
    title="AlphaNexus Backtesting API",
    version="0.1.0",
    description="Backtest simple trading strategies and return risk/performance analytics.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies")
def list_strategies() -> list[dict[str, str]]:
    return [
        {"id": "sma_crossover", "name": "SMA Crossover"},
        {"id": "rsi_mean_reversion", "name": "RSI Mean Reversion"},
        {"id": "bollinger_breakout", "name": "Bollinger Breakout"},
    ]


@app.post("/backtests", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest) -> BacktestResponse:
    if request.start >= request.end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        prices = fetch_prices(request.ticker.upper(), request.start, request.end, request.interval)
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
        result, metrics = run_backtest(prices, strategy_config, backtest_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        ["date", "close", "trade_signal", "shares", "cash", "portfolio_value", "realized_pnl"]
    ]

    return BacktestResponse(
        ticker=request.ticker.upper(),
        strategy=request.strategy,
        metrics=metrics,
        equity_curve=result[equity_columns].to_dict(orient="records"),
        trades=trades.to_dict(orient="records"),
    )
