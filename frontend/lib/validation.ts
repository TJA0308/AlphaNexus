import type { BacktestRequest } from "./types";

// Catches the mistakes a user can make with the form before a request is sent.
// The API enforces the same rules; this only saves a round trip and lets the
// Run button explain why it is disabled.
export function validateRequest(request: BacktestRequest): string | null {
  if (!request.ticker.trim()) return "Enter a ticker.";
  if (!request.start || !request.end) return "Choose a start and end date.";
  if (request.start >= request.end) return "Start date must be before end date.";
  if (!(request.starting_cash > 0)) return "Starting cash must be greater than 0.";
  if (request.fee_bps < 0 || request.slippage_bps < 0) return "Fees and slippage cannot be negative.";
  if (!(request.allocation > 0 && request.allocation <= 1)) return "Allocation must be between 1% and 100%.";

  if (request.strategy === "sma_crossover" && request.fast_window >= request.slow_window) {
    return "Fast SMA window must be shorter than the slow window.";
  }
  if (request.strategy === "rsi_mean_reversion") {
    if (request.rsi_window < 2) return "RSI window must be at least 2.";
    if (request.oversold <= 0 || request.overbought >= 100) return "RSI thresholds must be between 0 and 100.";
    if (request.oversold >= request.overbought) return "Oversold must be below overbought.";
  }
  if (request.strategy === "bollinger_breakout") {
    if (request.band_window < 2) return "Band window must be at least 2.";
    if (!(request.band_std > 0)) return "Band width must be greater than 0.";
  }

  return null;
}
