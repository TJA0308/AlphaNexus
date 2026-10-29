import type { BacktestRequest } from "./types";

// Catches the mistakes a user can make with the form before a request is sent.
// The API enforces the same rules; this only saves a round trip and lets the
// Run button explain why it is disabled.
export function validateRequest(request: BacktestRequest): string | null {
  if (!request.ticker.trim()) return "Enter a ticker.";
  if (!/^[A-Za-z0-9^][A-Za-z0-9.^=-]{0,19}$/.test(request.ticker) || /\s/.test(request.ticker)) {
    return "Enter one ticker, up to 20 characters, using letters, numbers, or . - ^ =";
  }
  if (!request.start || !request.end) return "Choose a start and end date.";
  if (request.start >= request.end) return "Start date must be before end date.";
  if (!(Number.isFinite(request.starting_cash) && request.starting_cash > 0 && request.starting_cash <= 1e12)) {
    return "Starting cash must be greater than 0 and at most 1 trillion.";
  }
  if (!(Number.isFinite(request.fee_bps) && Number.isFinite(request.slippage_bps)
    && request.fee_bps >= 0 && request.slippage_bps >= 0)) return "Fees and slippage cannot be negative or non-finite.";
  if (request.fee_bps > 1000 || request.slippage_bps > 1000) return "Fees and slippage must be at most 1,000 bps (10%).";
  if (!(request.allocation > 0 && request.allocation <= 1)) return "Allocation must be between 1% and 100%.";

  const validWindow = (value: number) => Number.isInteger(value) && value >= 2 && value <= 10_000;
  if (request.strategy === "sma_crossover") {
    if (!validWindow(request.fast_window) || !validWindow(request.slow_window)) {
      return "SMA windows must be integers between 2 and 10,000.";
    }
    if (!(request.fast_window < request.slow_window)) return "Fast SMA window must be shorter than the slow window.";
  }
  if (request.strategy === "rsi_mean_reversion") {
    if (!validWindow(request.rsi_window)) return "RSI window must be an integer between 2 and 10,000.";
    if (!(request.oversold > 0 && request.overbought < 100)) return "RSI thresholds must be between 0 and 100.";
    if (!(request.oversold < request.overbought)) return "Oversold must be below overbought.";
  }
  if (request.strategy === "bollinger_breakout") {
    if (!validWindow(request.band_window)) return "Band window must be an integer between 2 and 10,000.";
    if (!(request.band_std > 0 && request.band_std <= 100)) return "Band width must be greater than 0 and at most 100.";
  }

  return null;
}
