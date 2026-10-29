from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.data import TICKER_PATTERN, MarketDataUnavailable, fetch_prices
from alphanexus.experiments import engine_provenance, make_snapshot, results_match, snapshot_prices
from alphanexus.storage import get_experiment, recent_runs, save_run
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
    run_id: int | None = None
    saved: bool = False
    save_warning: str | None = None


class DatasetSnapshot(BaseModel):
    source: str
    captured_at: str
    downloaded_at: str | None
    sha256: str
    row_count: int
    actual_start: str
    actual_end: str
    price_policy: str
    timezone: str | None
    rows: list[dict[str, float | str]]


class ExperimentSnapshot(BaseModel):
    schema_version: int
    request: BacktestRequest
    engine: dict[str, str]
    dataset: DatasetSnapshot
    result: BacktestResponse


class SavedExperiment(BaseModel):
    id: int
    created_at: str
    snapshot: ExperimentSnapshot


class ReplayResponse(BaseModel):
    run_id: int
    matches: bool
    original_engine: dict[str, str]
    current_engine: dict[str, str]
    relative_tolerance: float = 1e-10
    absolute_tolerance: float = 1e-8
    result: BacktestResponse


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
    has_snapshot: bool


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
    try:
        return recent_runs(limit)
    except sqlite3.Error as exc:
        logger.exception("could not read run history")
        raise HTTPException(status_code=503, detail="Run history is temporarily unavailable.") from exc


def enforce_backtest_limit(http_request: Request) -> None:
    client = http_request.client.host if http_request.client else "unknown"
    retry_after = http_request.app.state.backtest_limiter.retry_after(client)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail=f"Too many backtests. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def configs(request: BacktestRequest) -> tuple[StrategyConfig, BacktestConfig]:
    strategy = StrategyConfig(
        name=request.strategy, fast_window=request.fast_window, slow_window=request.slow_window,
        rsi_window=request.rsi_window, oversold=request.oversold, overbought=request.overbought,
        band_window=request.band_window, band_std=request.band_std,
    )
    portfolio = BacktestConfig(
        starting_cash=request.starting_cash, fee_bps=request.fee_bps, slippage_bps=request.slippage_bps,
        allocation=request.allocation, interval=request.interval,
    )
    strategy.validate()
    portfolio.validate()
    return strategy, portfolio


def backtest_response(request: BacktestRequest, result: pd.DataFrame, metrics: dict) -> BacktestResponse:
    equity_columns = [
        "date", "close", "portfolio_value", "benchmark_value", "drawdown", "signal", "trade_signal",
    ]
    trades = result[result["trade_signal"] != 0][
        [
            "date", "signal_date", "close", "fill_price", "fee", "cash_before",
            "trade_signal", "trade_shares", "cash", "portfolio_value", "realized_pnl",
        ]
    ].rename(columns={"trade_shares": "shares"})
    return BacktestResponse(
        ticker=request.ticker.upper(), strategy=request.strategy, metrics=metrics,
        equity_curve=result[equity_columns].to_dict(orient="records"), trades=trades.to_dict(orient="records"),
    )


def result_payload(response: BacktestResponse) -> dict:
    return response.model_dump(mode="json", exclude={"run_id", "saved", "save_warning"})


def load_experiment(run_id: int) -> dict:
    try:
        experiment = get_experiment(run_id)
    except sqlite3.Error as exc:
        logger.exception("could not read experiment")
        raise HTTPException(status_code=503, detail="Saved experiments are temporarily unavailable.") from exc
    if experiment is None:
        raise HTTPException(status_code=404, detail="Run not found. It may have expired from shared history.")
    if experiment["snapshot"] is None:
        raise HTTPException(status_code=409, detail="This legacy run has only a summary; its inputs were not saved.")
    return experiment


@app.get("/backtests/{run_id}", response_model=SavedExperiment)
def read_experiment(run_id: int) -> SavedExperiment:
    experiment = SavedExperiment.model_validate(load_experiment(run_id))
    experiment.snapshot.result.run_id = run_id
    experiment.snapshot.result.saved = True
    return experiment


@app.post("/backtests/{run_id}/replay", response_model=ReplayResponse)
def replay_experiment(run_id: int, http_request: Request) -> ReplayResponse:
    enforce_backtest_limit(http_request)
    snapshot = load_experiment(run_id)["snapshot"]
    try:
        prices = snapshot_prices(snapshot)
        request = BacktestRequest.model_validate(snapshot["request"])
        strategy, portfolio = configs(request)
        result, metrics = run_backtest(prices, strategy, portfolio)
        response = backtest_response(request, result, metrics)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Cannot replay this saved experiment: {exc}") from exc
    return ReplayResponse(
        run_id=run_id, matches=results_match(snapshot["result"], result_payload(response)),
        original_engine=snapshot["engine"], current_engine=engine_provenance(), result=response,
    )


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
    enforce_backtest_limit(http_request)
    if request.start >= request.end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        strategy_config, backtest_config = configs(request)
        prices = fetch_prices(request.ticker.upper(), request.start, request.end, request.interval)
        result, metrics = run_backtest(prices, strategy_config, backtest_config)
    except MarketDataUnavailable as exc:
        # The upstream provider is down or rate-limiting us. Nothing the caller
        # sent is wrong, so this is a gateway failure, not a bad request.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = backtest_response(request, result, metrics)
    # Commit the summary and complete experiment in one transaction.
    # The dashboard runs a default backtest for every visitor on first load;
    # saving those would bury real runs under identical copies.
    if save:
        try:
            normalized_request = request.model_dump(mode="json")
            normalized_request["ticker"] = request.ticker.upper()
            snapshot = make_snapshot(normalized_request, prices, result_payload(response))
            response.run_id = save_run(
                ticker=request.ticker.upper(),
                strategy=request.strategy,
                start_date=str(request.start),
                end_date=str(request.end),
                interval=request.interval,
                metrics=metrics,
                snapshot=snapshot,
            )
            response.saved = True
        except (sqlite3.Error, ValueError):
            # History is a convenience; a locked or read-only database should
            # not throw away a backtest that already succeeded.
            logger.exception("could not save backtest run to history")
            response.save_warning = (
                "Result calculated, but not saved. Storage is unavailable or the experiment is too large."
            )
    return response
