// Mirrors the Pydantic models in api/main.py. Keep the two in step: the API's
// OpenAPI schema at /docs is the source of truth.

export type Strategy = "sma_crossover" | "rsi_mean_reversion" | "bollinger_breakout";

export type BarInterval = "1d" | "1h";

export type BacktestRequest = {
  ticker: string;
  start: string;
  end: string;
  interval: BarInterval;
  strategy: Strategy;
  starting_cash: number;
  fee_bps: number;
  slippage_bps: number;
  allocation: number;
  fast_window: number;
  slow_window: number;
  rsi_window: number;
  oversold: number;
  overbought: number;
  band_window: number;
  band_std: number;
};

export type Metrics = {
  total_return: number;
  benchmark_return: number;
  excess_return_vs_benchmark: number;
  max_drawdown: number;
  sharpe_ratio: number;
  trade_count: number;
  win_rate: number;
  ending_equity: number;
};

export type EquityPoint = {
  date: string;
  close: number;
  portfolio_value: number;
  benchmark_value: number;
  drawdown: number;
  signal: number;
  trade_signal: number;
};

export type Trade = {
  date: string;
  signal_date: string;
  close: number;
  fill_price: number;
  fee: number;
  cash_before: number;
  trade_signal: number;
  shares: number;
  cash: number;
  portfolio_value: number;
  realized_pnl: number;
};

export type BacktestResponse = {
  ticker: string;
  strategy: Strategy;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  trades: Trade[];
  run_id: number | null;
  saved: boolean;
  save_warning: string | null;
};

export type SavedExperiment = {
  id: number;
  created_at: string;
  snapshot: {
    schema_version: number;
    request: BacktestRequest;
    engine: Record<string, string>;
    dataset: {
      source: string;
      captured_at: string;
      downloaded_at: string | null;
      sha256: string;
      row_count: number;
      actual_start: string;
      actual_end: string;
      price_policy: string;
      timezone: string | null;
      rows: Record<string, string | number>[];
    };
    result: BacktestResponse;
  };
};

export type ReplayResponse = {
  run_id: number;
  matches: boolean;
  original_engine: Record<string, string>;
  current_engine: Record<string, string>;
  relative_tolerance: number;
  absolute_tolerance: number;
  result: BacktestResponse;
};

export type RunSummary = {
  id: number;
  created_at: string;
  ticker: string;
  strategy: Strategy;
  start_date: string;
  end_date: string;
  interval: BarInterval;
  total_return: number;
  benchmark_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  trade_count: number;
  has_snapshot: boolean;
};

export const STRATEGY_LABELS: Record<Strategy, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_breakout: "Bollinger Breakout",
};
