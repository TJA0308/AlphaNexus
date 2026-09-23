"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DrawdownChart, EquityChart, type ChartPoint } from "../components/Charts";
import { ControlsPanel } from "../components/ControlsPanel";
import { DataTable } from "../components/DataTable";
import { MetricsGrid } from "../components/MetricsGrid";
import { RunHistory } from "../components/RunHistory";
import { fetchRuns, runBacktest } from "../lib/api";
import { barLabel, dollars, percent, toCsv } from "../lib/format";
import { STRATEGY_LABELS, type BacktestRequest, type BacktestResponse, type RunSummary } from "../lib/types";
import { validateRequest } from "../lib/validation";

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function trailingYear() {
  const today = new Date();
  const oneYearAgo = new Date(today);
  oneYearAgo.setFullYear(today.getFullYear() - 1);
  return { start: isoDate(oneYearAgo), end: isoDate(today) };
}

// The page is prerendered at build time, so anything derived from "today"
// would bake the build date into the HTML and then disagree with the browser
// during hydration. The date range is therefore filled in after mount.
const INITIAL_FORM: BacktestRequest = {
  ticker: "AAPL",
  start: "",
  end: "",
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

function csvHref(rows: Record<string, string | number>[]) {
  return `data:text/csv;charset=utf-8,${encodeURIComponent(toCsv(rows))}`;
}

// A result is kept together with the request that produced it, so the badges
// and assumptions describe the run on screen even after the form is edited.
type CompletedRun = { request: BacktestRequest; response: BacktestResponse };

export default function Page() {
  const [form, setForm] = useState<BacktestRequest>(INITIAL_FORM);
  const [run, setRun] = useState<CompletedRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [historyError, setHistoryError] = useState("");

  const validationError = validateRequest(form);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await fetchRuns());
      setHistoryError("");
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Could not load run history.");
    }
  }, []);

  useEffect(() => {
    setForm((current) => (current.start || current.end ? current : { ...current, ...trailingYear() }));
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  async function handleRun() {
    if (validationError) return;
    const request = { ...form, ticker: form.ticker.trim() };

    setLoading(true);
    setError("");
    try {
      const response = await runBacktest(request);
      setRun({ request, response });
      void loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = useMemo<ChartPoint[]>(
    () =>
      run?.response.equity_curve.map((point) => ({
        label: barLabel(point.date, run.request.interval),
        portfolio_value: point.portfolio_value,
        benchmark_value: point.benchmark_value,
        drawdownPercent: point.drawdown * 100,
      })) ?? [],
    [run],
  );

  const metrics = run?.response.metrics ?? null;

  const tradeRows = useMemo(
    () =>
      run?.response.trades
        .slice()
        .reverse()
        .map((trade) => ({
          date: barLabel(trade.date, run.request.interval),
          side: trade.trade_signal > 0 ? "Buy" : "Sell",
          price: dollars(trade.close),
          shares: trade.shares.toFixed(4),
          portfolio: dollars(trade.portfolio_value),
          realized_pnl: trade.trade_signal < 0 ? dollars(trade.realized_pnl) : "",
        })) ?? [],
    [run],
  );

  const exports = useMemo(() => {
    if (!run) return null;
    const prefix = `${run.response.ticker.toLowerCase()}_${run.response.strategy}`;
    return {
      equity: {
        name: `${prefix}_equity_curve.csv`,
        href: csvHref(
          run.response.equity_curve.map((point) => ({
            date: point.date,
            close: point.close,
            portfolio_value: point.portfolio_value,
            benchmark_value: point.benchmark_value,
            drawdown: point.drawdown,
            signal: point.signal,
            trade_signal: point.trade_signal,
          })),
        ),
      },
      trades: {
        name: `${prefix}_trades.csv`,
        href: csvHref(
          run.response.trades.map((trade) => ({
            date: trade.date,
            side: trade.trade_signal > 0 ? "Buy" : "Sell",
            price: trade.close,
            shares: trade.shares,
            portfolio_value: trade.portfolio_value,
            realized_pnl: trade.realized_pnl,
          })),
        ),
      },
    };
  }, [run]);

  const status = error ? (
    <span className="error">{error}</span>
  ) : validationError ? (
    <span className="warning">{validationError}</span>
  ) : loading ? (
    "Running backtest…"
  ) : run ? (
    `${run.response.ticker} result loaded`
  ) : (
    "Ready to run"
  );

  return (
    <main className="shell">
      <ControlsPanel form={form} onChange={(patch) => setForm((current) => ({ ...current, ...patch }))} />

      <section className="content">
        <div className="topbar">
          <div>
            <p className="eyebrow">Strategy research</p>
            <h2>Performance Dashboard</h2>
            <p className="muted">Compare a configurable strategy against buy-and-hold with explicit cost assumptions.</p>
          </div>
          <div className="top-actions">
            <div className="status" role="status" aria-live="polite">
              {status}
            </div>
            <button className="primary-button" onClick={handleRun} disabled={loading || Boolean(validationError)}>
              {loading ? "Running..." : "Run Backtest"}
            </button>
          </div>
        </div>

        {run ? (
          <div className="badge-row">
            {[
              run.response.ticker,
              STRATEGY_LABELS[run.request.strategy],
              `${run.request.start} → ${run.request.end}`,
              `${run.request.interval} bars`,
              `${run.request.fee_bps} bps fee`,
              `${run.request.slippage_bps} bps slippage`,
            ].map((badge) => (
              <span className="badge" key={badge}>
                {badge}
              </span>
            ))}
          </div>
        ) : null}

        {metrics && metrics.excess_return_vs_benchmark < 0 ? (
          <div className="alert-banner">
            Strategy underperformed buy-and-hold by {percent(-metrics.excess_return_vs_benchmark)} over the selected period.
          </div>
        ) : null}

        <MetricsGrid metrics={metrics} />

        <Tabs.Root className="tabs-root" defaultValue="performance">
          <Tabs.List className="tabs-list" aria-label="Dashboard sections">
            <Tabs.Trigger className="tabs-trigger" value="performance">
              Performance
            </Tabs.Trigger>
            <Tabs.Trigger className="tabs-trigger" value="trades">
              Trades
            </Tabs.Trigger>
            <Tabs.Trigger className="tabs-trigger" value="history">
              History
            </Tabs.Trigger>
            <Tabs.Trigger className="tabs-trigger" value="assumptions">
              Assumptions
            </Tabs.Trigger>
            <Tabs.Trigger className="tabs-trigger" value="exports">
              Exports
            </Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content className="tabs-content" value="performance">
            <div className="grid">
              <section className="panel">
                <div className="panel-header">
                  <h3>Equity Curve</h3>
                  <span className="muted">Strategy vs. buy-and-hold</span>
                </div>
                <div className="chart">
                  <EquityChart data={chartData} />
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h3>Drawdown</h3>
                  <span className="muted">Peak-to-trough decline</span>
                </div>
                <div className="chart small">
                  <DrawdownChart data={chartData} />
                </div>
              </section>
            </div>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="trades">
            <section className="panel">
              <div className="panel-header">
                <h3>Trade Ledger</h3>
                <span className="muted">
                  {tradeRows.length ? `${tradeRows.length} executions, newest first` : "Executed entries and exits"}
                </span>
              </div>
              <div className="scroll-table">
                <DataTable rows={tradeRows} emptyMessage={run ? "This run made no trades." : "No trades to display yet."} />
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="history">
            <RunHistory runs={history} error={historyError} onRefresh={() => void loadHistory()} />
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="assumptions">
            <section className="panel assumptions">
              <div>
                <h3>Execution Model</h3>
                <p>
                  The simulator is long-only and moves between cash and one position. A signal computed from a bar&apos;s
                  close is executed at the next bar&apos;s close, so no trade uses information it could not have had.
                  Fees and slippage are charged on every execution. Buy-and-hold is shown without costs.
                </p>
              </div>
              <div>
                <h3>Parameters of the Displayed Run</h3>
                {run ? (
                  <ul>
                    <li>Ticker: {run.response.ticker}</li>
                    <li>Strategy: {STRATEGY_LABELS[run.request.strategy]}</li>
                    <li>
                      Date range: {run.request.start} to {run.request.end} ({run.request.interval} bars)
                    </li>
                    <li>Starting cash: {dollars(run.request.starting_cash)}</li>
                    <li>Allocation per entry: {percent(run.request.allocation)}</li>
                    <li>
                      Costs: {run.request.fee_bps} bps fee, {run.request.slippage_bps} bps slippage
                    </li>
                  </ul>
                ) : (
                  <p className="muted">Run a backtest to see the parameters it used.</p>
                )}
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="exports">
            <section className="panel export-panel">
              <h3>Export Results</h3>
              <p className="muted">Download the displayed result for documentation or follow-up analysis.</p>
              {exports ? (
                <div className="export-actions">
                  <a className="secondary-button" href={exports.equity.href} download={exports.equity.name}>
                    Equity Curve CSV
                  </a>
                  <a className="secondary-button" href={exports.trades.href} download={exports.trades.name}>
                    Trade Ledger CSV
                  </a>
                </div>
              ) : (
                <p className="muted">Exports become available after a completed run.</p>
              )}
            </section>
          </Tabs.Content>
        </Tabs.Root>
      </section>
    </main>
  );
}
