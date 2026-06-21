from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.data import fetch_prices
from alphanexus.strategies import StrategyConfig
from styles import apply_custom_theme


ASSET_POOL = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Nvidia": "NVDA",
    "Amazon": "AMZN",
    "Alphabet": "GOOGL",
    "Bitcoin": "BTC-USD",
}

STRATEGY_LABELS = {
    "SMA Crossover": "sma_crossover",
    "RSI Mean Reversion": "rsi_mean_reversion",
    "Bollinger Breakout": "bollinger_breakout",
}


st.set_page_config(page_title="AlphaNexus Backtesting Lab", layout="wide")
apply_custom_theme()


@st.cache_data(ttl=900)
def load_prices(ticker: str, start: date, end: date, interval: str) -> pd.DataFrame:
    return fetch_prices(ticker, start, end, interval)


def format_percent(value: float) -> str:
    return f"{value * 100:,.2f}%"


def build_equity_chart(result: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=result["date"],
            y=result["portfolio_value"],
            mode="lines",
            name="Strategy",
            line={"color": "#2f80ed", "width": 3},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=result["date"],
            y=result["benchmark_value"],
            mode="lines",
            name="Buy and hold",
            line={"color": "#9aa4b2", "width": 2, "dash": "dot"},
        )
    )
    fig.update_layout(
        height=430,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        legend={"orientation": "h", "y": 1.05},
        yaxis_title="Portfolio value",
    )
    return fig


def build_drawdown_chart(result: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=result["date"],
            y=result["drawdown"] * 100,
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            line={"color": "#d64545", "width": 2},
        )
    )
    fig.update_layout(
        height=260,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        yaxis_title="Drawdown %",
        showlegend=False,
    )
    return fig


def build_price_chart(result: pd.DataFrame) -> go.Figure:
    buys = result[result["trade_signal"] > 0]
    sells = result[result["trade_signal"] < 0]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=result["date"],
            y=result["close"],
            mode="lines",
            name="Close",
            line={"color": "#d4d9e2", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=buys["date"],
            y=buys["close"],
            mode="markers",
            name="Buy",
            marker={"color": "#22c55e", "size": 10, "symbol": "triangle-up"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sells["date"],
            y=sells["close"],
            mode="markers",
            name="Sell",
            marker={"color": "#ef4444", "size": 10, "symbol": "triangle-down"},
        )
    )
    fig.update_layout(
        height=360,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        legend={"orientation": "h", "y": 1.05},
        yaxis_title="Close price",
    )
    return fig


st.title("AlphaNexus Backtesting Lab")
st.caption("Research simple trading rules, compare them with buy-and-hold, and inspect risk assumptions.")

with st.sidebar:
    st.header("Backtest setup")
    selected_asset = st.selectbox("Asset", list(ASSET_POOL.keys()))
    ticker = ASSET_POOL[selected_asset]
    strategy_label = st.selectbox("Strategy", list(STRATEGY_LABELS.keys()))
    strategy_name = STRATEGY_LABELS[strategy_label]

    st.divider()
    interval = st.selectbox("Interval", ["1d", "1h"], index=0)
    default_start = date.today() - timedelta(days=365)
    start_date = st.date_input("Start date", value=default_start)
    end_date = st.date_input("End date", value=date.today())

    st.divider()
    starting_cash = st.number_input("Starting cash", min_value=1000, value=10000, step=1000)
    fee_bps = st.slider("Fee, basis points", 0, 50, 5)
    slippage_bps = st.slider("Slippage, basis points", 0, 50, 5)
    allocation = st.slider("Capital allocation", 10, 100, 100) / 100

    st.divider()
    if strategy_name == "sma_crossover":
        fast_window = st.slider("Fast SMA window", 5, 50, 20)
        slow_window = st.slider("Slow SMA window", 20, 200, 50)
        strategy_config = StrategyConfig(
            name="sma_crossover",
            fast_window=fast_window,
            slow_window=slow_window,
        )
    elif strategy_name == "rsi_mean_reversion":
        rsi_window = st.slider("RSI window", 5, 40, 14)
        oversold = st.slider("Oversold threshold", 10, 45, 30)
        overbought = st.slider("Overbought threshold", 55, 90, 70)
        strategy_config = StrategyConfig(
            name="rsi_mean_reversion",
            rsi_window=rsi_window,
            oversold=oversold,
            overbought=overbought,
        )
    else:
        band_window = st.slider("Band window", 10, 80, 20)
        band_std = st.slider("Band width", 0.5, 3.0, 2.0, 0.1)
        strategy_config = StrategyConfig(
            name="bollinger_breakout",
            band_window=band_window,
            band_std=band_std,
        )

    run_clicked = st.button("Run backtest", type="primary", use_container_width=True)

if start_date >= end_date:
    st.error("Start date must be before end date.")
elif not run_clicked:
    st.info("Choose an asset and strategy, then run a backtest.")
else:
    try:
        prices = load_prices(ticker, start_date, end_date, interval)
        result, metrics = run_backtest(
            prices,
            strategy_config,
            BacktestConfig(
                starting_cash=float(starting_cash),
                fee_bps=float(fee_bps),
                slippage_bps=float(slippage_bps),
                allocation=float(allocation),
                interval=interval,
            ),
        )
    except Exception as exc:
        st.error(f"Could not run backtest: {exc}")
        st.stop()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Ending equity", f"${metrics['ending_equity']:,.2f}")
    metric_cols[1].metric("Strategy return", format_percent(metrics["total_return"]))
    metric_cols[2].metric("Benchmark", format_percent(metrics["benchmark_return"]))
    metric_cols[3].metric("Max drawdown", format_percent(metrics["max_drawdown"]))
    metric_cols[4].metric("Sharpe", f"{metrics['sharpe_ratio']:.2f}")
    metric_cols[5].metric("Win rate", format_percent(metrics["win_rate"]))

    st.markdown(
        f"""
        <div class="assumption-bar">
            <span>{ticker}</span>
            <span>{strategy_label}</span>
            <span>{interval} bars</span>
            <span>{fee_bps} bps fee</span>
            <span>{slippage_bps} bps slippage</span>
            <span>{metrics['trade_count']} completed trades</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_overview, tab_trades, tab_data = st.tabs(["Overview", "Trades", "Data"])
    with tab_overview:
        st.plotly_chart(build_equity_chart(result), use_container_width=True)
        left, right = st.columns([2, 1])
        with left:
            st.plotly_chart(build_price_chart(result), use_container_width=True)
        with right:
            st.plotly_chart(build_drawdown_chart(result), use_container_width=True)

    with tab_trades:
        trades = result[result["trade_signal"] != 0][
            ["date", "close", "trade_signal", "shares", "cash", "portfolio_value", "realized_pnl"]
        ].copy()
        trades["side"] = trades["trade_signal"].map({1: "Buy", -1: "Sell"})
        st.dataframe(
            trades[["date", "side", "close", "shares", "cash", "portfolio_value", "realized_pnl"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab_data:
        st.dataframe(result.tail(250), use_container_width=True, hide_index=True)
