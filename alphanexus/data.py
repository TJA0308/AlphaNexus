from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def normalize_prices(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        raise ValueError("market data provider returned no rows")

    df = raw.copy().reset_index()
    df.columns = [str(column).lower().replace(" ", "_") for column in df.columns]
    if "datetime" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"datetime": "date"})
    if "adj_close" in df.columns and "close" not in df.columns:
        df = df.rename(columns={"adj_close": "close"})

    missing = set(REQUIRED_COLUMNS).difference(df.columns)
    if missing:
        raise ValueError(f"market data missing required columns: {sorted(missing)}")

    return df[REQUIRED_COLUMNS].dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def fetch_prices(
    ticker: str,
    start: date | str,
    end: date | str,
    interval: str = "1d",
) -> pd.DataFrame:
    raw = yf.download(
        ticker,
        start=str(start),
        end=str(end),
        interval=interval,
        auto_adjust=False,
        progress=False,
        multi_level_index=False,
    )
    return normalize_prices(raw)

