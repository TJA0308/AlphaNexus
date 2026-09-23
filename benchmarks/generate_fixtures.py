from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ROW_COUNT = 504
START_DATE = date(2023, 1, 3)


def business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def close_price(asset: str, index: int) -> float:
    if asset == "trend_up":
        value = 100 + 0.14 * index + 2.8 * math.sin(index / 14)
    elif asset == "trend_down":
        value = 150 - 0.08 * index + 3.2 * math.sin(index / 18)
    elif asset == "mean_revert":
        value = 90 + 8.0 * math.sin(index / 9) + 2.2 * math.sin(index / 31)
    elif asset == "volatile":
        value = 105 + 0.03 * index + 10.0 * math.sin(index / 7) + 4.0 * math.sin(index / 3)
    elif asset == "breakout":
        breakout = max(index - 240, 0) * 0.16
        value = 70 + 0.02 * index + breakout + 3.0 * math.sin(index / 20)
    elif asset == "cyclical":
        value = 120 + 12.0 * math.sin(index / 21) + 4.5 * math.sin(index / 5)
    elif asset == "flat_noise":
        value = 95 + 1.8 * math.sin(index * 1.7) + 0.7 * math.sin(index / 3)
    elif asset == "shock_recovery":
        shock = -28 if 190 <= index <= 230 else 0
        recovery = max(index - 230, 0) * 0.11
        value = 112 + 0.04 * index + shock + recovery + 2.5 * math.sin(index / 16)
    else:
        raise ValueError(f"unknown fixture asset: {asset}")

    return round(max(value, 5), 4)


def build_rows(asset: str) -> list[dict[str, str | float | int]]:
    days = business_days(START_DATE, ROW_COUNT)
    closes = [close_price(asset, index) for index in range(ROW_COUNT)]
    rows: list[dict[str, str | float | int]] = []

    for index, day in enumerate(days):
        close = closes[index]
        previous_close = closes[index - 1] if index else close
        open_price = round(previous_close * (1 + 0.0015 * math.sin(index / 6)), 4)
        high = round(max(open_price, close) * (1.006 + 0.001 * abs(math.sin(index / 11))), 4)
        low = round(min(open_price, close) * (0.994 - 0.001 * abs(math.cos(index / 13))), 4)
        volume = int(900_000 + 80_000 * abs(math.sin(index / 8)) + index * 137)

        rows.append(
            {
                "date": day.isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return rows


def write_fixture(asset: str) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{asset}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(build_rows(asset))


def main() -> int:
    for asset in FIXTURE_ASSETS:
        write_fixture(asset)
    return 0


FIXTURE_ASSETS = [
    "trend_up",
    "trend_down",
    "mean_revert",
    "volatile",
    "breakout",
    "cyclical",
    "flat_noise",
    "shock_recovery",
]


if __name__ == "__main__":
    raise SystemExit(main())
