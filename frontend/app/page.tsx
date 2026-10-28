"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DrawdownChart, EquityChart, type ChartPoint } from "../components/Charts";
import { ControlsPanel } from "../components/ControlsPanel";
import { DataTable } from "../components/DataTable";
import { MetricsGrid } from "../components/MetricsGrid";
import { RunHistory } from "../components/RunHistory";
import { API_BASE, fetchExperiment, fetchRuns, replayExperiment, runBacktest } from "../lib/api";
import { barLabel, dollars, percent, toCsv } from "../lib/format";
import { SLOW_REQUEST_MS, loadingMessage } from "../lib/status";
import { STRATEGY_LABELS, type BacktestRequest, type BacktestResponse, type RunSummary } from "../lib/types";
import { validateRequest } from "../lib/validation";

function isoDate(value: Date) {
  // Local calendar date; toISOString() is UTC and can be a day off.
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
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

// Builds the CSV only when a download is requested, not on every run.
function downloadCsv(name: string, rows: () => Record<string, string | number>[]) {
  const url = URL.createObjectURL(new Blob([toCsv(rows())], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

// A result is kept together with the request that produced it, so the badges
// and assumptions describe the run on screen even after the form is edited.
type CompletedRun = { request: BacktestRequest; response: BacktestResponse };

export default function Page() {
  const [form, setForm] = useState<BacktestRequest>(INITIAL_FORM);
  const [run, setRun] = useState<CompletedRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [tab, setTab] = useState("performance");
  const [notice, setNotice] = useState("");

  const validationError = validateRequest(form);

  // Flag a request that is taking long enough to be a cold start, so the
  // status can explain the wait instead of looking stuck.
  useEffect(() => {
    if (!loading) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_REQUEST_MS);
    return () => clearTimeout(timer);
  }, [loading]);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await fetchRuns());
      setHistoryError("");
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Could not load run history.");
    }
  }, []);

  const execute = useCallback(
    async (request: BacktestRequest, { save }: { save: boolean }) => {
      setLoading(true);
      setError("");
      setNotice("");
      try {
        const response = await runBacktest(request, { save });
        setRun({ request, response });
        setTab("performance");
        if (save) void loadHistory();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Backtest failed.");
      } finally {
        setLoading(false);
      }
    },
    [loadHistory],
  );

  // A first-time visitor should see a result, not an empty dashboard, so the
  // default configuration runs once on mount. It is not saved to the shared
  // history, which would otherwise fill with identical runs. The ref stops
  // React's development-mode double effect from running it twice.
  const autoRunStarted = useRef(false);
  useEffect(() => {
    if (autoRunStarted.current) return;
    autoRunStarted.current = true;

    const initial = { ...INITIAL_FORM, ...trailingYear() };
    setForm((current) => (current.start || current.end ? current : initial));
    void execute(initial, { save: false });
  }, [execute]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  function handleRun() {
    if (validationError || loading) return;
    void execute({ ...form, ticker: form.ticker.trim() }, { save: true });
  }

  async function openSaved(id: number, clone = false) {
    if (loading) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const experiment = await fetchExperiment(id);
      setForm(experiment.snapshot.request);
      if (clone) {
        setNotice(`Settings copied from run #${id}. Edit them and run a new experiment; displayed results are unchanged.`);
      } else {
        setRun({ request: experiment.snapshot.request, response: experiment.snapshot.result });
        setNotice(`Opened saved run #${id} using its original results.`);
      }
      setTab("performance");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the experiment.");
    } finally {
      setLoading(false);
    }
  }

  async function savedAction(action: "replay" | "export") {
    const id = run?.response.run_id;
    if (id == null || loading) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      if (action === "replay") {
        const replay = await replayExperiment(id);
        setNotice(replay.matches
          ? `Replay verified for run #${id}: all metrics, equity points and trades match within numerical tolerances.`
          : `Replay differs for run #${id}. The current engine does not reproduce the saved result. Original results are unchanged.`);
      } else {
        const experiment = await fetchExperiment(id);
        const url = URL.createObjectURL(new Blob([JSON.stringify(experiment, null, 2)], { type: "application/json" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = `alphanexus_run_${id}.json`;
        link.click();
        URL.revokeObjectURL(url);
        setNotice(`Exported run #${id} with settings, input prices, provenance and results.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not access the saved experiment.");
    } finally {
      setLoading(false);
    }
  }

  // The settings Run button is at the bottom of the page on phones; bring the
  // results back into view so the user sees the run start and finish.
  function handleRunFromSettings() {
    handleRun();
    window.scrollTo({ top: 0, behavior: "smooth" });
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
          signal_date: barLabel(trade.signal_date, run.request.interval),
          side: trade.trade_signal > 0 ? "Buy" : "Sell",
          reference_close: dollars(trade.close),
          fill_price: dollars(trade.fill_price),
          fee: dollars(trade.fee),
          shares: trade.shares.toFixed(4),
          cash_before: dollars(trade.cash_before),
          cash_after: dollars(trade.cash),
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
        rows: () =>
          run.response.equity_curve.map((point) => ({
            date: point.date,
            close: point.close,
            portfolio_value: point.portfolio_value,
            benchmark_value: point.benchmark_value,
            drawdown: point.drawdown,
            signal: point.signal,
            trade_signal: point.trade_signal,
          })),
      },
      trades: {
        name: `${prefix}_trades.csv`,
        rows: () =>
          run.response.trades.map((trade) => ({
            date: trade.date,
            side: trade.trade_signal > 0 ? "Buy" : "Sell",
            signal_date: trade.signal_date,
            reference_close: trade.close,
            fill_price: trade.fill_price,
            fee: trade.fee,
            shares: trade.shares,
            cash_before: trade.cash_before,
            cash_after: trade.cash,
            portfolio_value: trade.portfolio_value,
            realized_pnl: trade.realized_pnl,
          })),
      },
    };
  }, [run]);

  const status = error ? (
    <span className="error">{error}</span>
  ) : validationError ? (
    <span className="warning">{validationError}</span>
  ) : loading ? (
    loadingMessage({ hasResult: Boolean(run), slow })
  ) : run ? (
    `${run.response.ticker} result loaded`
  ) : (
    "Ready to run"
  );

  return (
    <main className="shell">
      <ControlsPanel
        form={form}
        onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
        onRun={handleRunFromSettings}
        runDisabled={loading || Boolean(validationError)}
      />

      <section className="content">
        <div className="topbar">
          <div>
            <p className="eyebrow">Strategy research</p>
            <h2>Performance Dashboard</h2>
            <p className="muted">Compare a configurable strategy against buy-and-hold with explicit cost assumptions.</p>
            <a className="settings-link mobile-only" href="#settings">
              Change ticker, strategy, and costs ↓
            </a>
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

        {run ? (
          <div className="panel">
            <p className={run.response.save_warning ? "warning" : "muted"}>
              {run.response.save_warning ?? (run.response.saved
                ? `Saved experiment #${run.response.run_id}. Inputs and results are preserved in shared history.`
                : "This result is not saved in history.")}
            </p>
            {run.response.saved && run.response.run_id != null ? (
              <div className="export-actions">
                <button className="secondary-button" disabled={loading} onClick={() => void savedAction("replay")}>
                  Verify replay
                </button>
                <button className="secondary-button" disabled={loading} onClick={() => void savedAction("export")}>
                  Export experiment JSON
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        {notice ? <p role="status" className="muted">{notice}</p> : null}

        <MetricsGrid metrics={metrics} />

        <Tabs.Root className="tabs-root" value={tab} onValueChange={setTab}>
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
              <p className="muted">
                Fill price includes slippage; fees are charged separately. Cash after = cash before
                minus quantity × fill price and fee for buys, or plus sale proceeds minus fee for sells.
                CSV exports retain full precision and the signal timestamp.
              </p>
              <div className="scroll-table">
                <DataTable rows={tradeRows} emptyMessage={run ? "This run made no trades." : "No trades to display yet."} />
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="history">
            <RunHistory runs={history} error={historyError} onRefresh={() => void loadHistory()}
              busy={loading} onOpen={(id) => void openSaved(id)} onClone={(id) => void openSaved(id, true)} />
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="assumptions">
            <section className="panel assumptions">
              <div>
                <h3>Execution Model</h3>
                <p>
                  The simulator is long-only and moves between cash and one position. A signal computed from a bar&apos;s
                  close is executed at the next bar&apos;s close, so no trade uses information it could not have had.
                  Fees and slippage are charged on every execution. Buy-and-hold is shown without costs.
                  Prices exclude dividend income. Open positions are marked to the final close without liquidation costs.
                  Annualization assumes US equity sessions (252 days); currency displays assume USD.
                  Other markets and currencies are not modeled. RSI uses an SMA seed followed by Wilder smoothing.
                </p>
              </div>
              <div>
                <h3>Parameters of the Displayed Run</h3>
                {run ? (
                  <ul>
                    <li>Ticker: {run.response.ticker}</li>
                    <li>Strategy: {STRATEGY_LABELS[run.request.strategy]}</li>
                    {run.request.strategy === "sma_crossover" ? (
                      <li>SMA windows: {run.request.fast_window} fast / {run.request.slow_window} slow bars</li>
                    ) : run.request.strategy === "rsi_mean_reversion" ? (
                      <li>RSI: {run.request.rsi_window} bars; enter below {run.request.oversold}, exit above {run.request.overbought}</li>
                    ) : (
                      <li>Bollinger bands: {run.request.band_window} bars, {run.request.band_std} standard deviations</li>
                    )}
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
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => downloadCsv(exports.equity.name, exports.equity.rows)}
                  >
                    Equity Curve CSV
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => downloadCsv(exports.trades.name, exports.trades.rows)}
                  >
                    Trade Ledger CSV
                  </button>
                </div>
              ) : (
                <p className="muted">Exports become available after a completed run.</p>
              )}
            </section>
          </Tabs.Content>
        </Tabs.Root>

        <footer className="footer">
          <span>Built by Tejasv Agarwal</span>
          <a href="https://github.com/TJA0308/AlphaNexus" target="_blank" rel="noreferrer">
            Source on GitHub
          </a>
          <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
            API docs
          </a>
          <span className="muted">Research and education only. Not financial advice.</span>
        </footer>
      </section>
    </main>
  );
}
