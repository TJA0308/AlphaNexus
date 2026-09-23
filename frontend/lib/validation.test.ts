import { describe, expect, it } from "vitest";

import type { BacktestRequest } from "./types";
import { validateRequest } from "./validation";

const valid: BacktestRequest = {
  ticker: "AAPL",
  start: "2024-01-01",
  end: "2024-12-31",
  interval: "1d",
  strategy: "sma_crossover",
  starting_cash: 10_000,
  fee_bps: 5,
  slippage_bps: 5,
  allocation: 1,
  fast_window: 17,
  slow_window: 50,
  rsi_window: 14,
  oversold: 30,
  overbought: 70,
  band_window: 20,
  band_std: 2,
};

describe("validateRequest", () => {
  it("accepts the default form", () => {
    expect(validateRequest(valid)).toBeNull();
  });

  it.each<[string, Partial<BacktestRequest>, RegExp]>([
    ["a blank ticker", { ticker: "  " }, /ticker/i],
    ["a start on the end date", { end: "2024-01-01" }, /before end/i],
    ["a start after the end", { start: "2025-01-01" }, /before end/i],
    ["zero starting cash", { starting_cash: 0 }, /starting cash/i],
    ["an emptied cash box (NaN)", { starting_cash: Number.NaN }, /starting cash/i],
    ["negative fees", { fee_bps: -1 }, /negative/i],
    ["allocation above 100%", { allocation: 1.5 }, /allocation/i],
    ["fast SMA not below slow", { fast_window: 50, slow_window: 50 }, /fast sma/i],
  ])("rejects %s", (_name, patch, message) => {
    expect(validateRequest({ ...valid, ...patch })).toMatch(message);
  });

  it("checks RSI thresholds only for the RSI strategy", () => {
    const inverted = { ...valid, oversold: 80, overbought: 20 };
    expect(validateRequest(inverted)).toBeNull();
    expect(validateRequest({ ...inverted, strategy: "rsi_mean_reversion" })).toMatch(/oversold/i);
  });

  it("checks band settings only for the Bollinger strategy", () => {
    const badBands = { ...valid, band_std: 0 };
    expect(validateRequest(badBands)).toBeNull();
    expect(validateRequest({ ...badBands, strategy: "bollinger_breakout" })).toMatch(/band width/i);
  });
});
