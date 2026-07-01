"use client";

import * as Slider from "@radix-ui/react-slider";
import * as Tabs from "@radix-ui/react-tabs";
import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Strategy = "sma_crossover" | "rsi_mean_reversion" | "bollinger_breakout";

type EquityPoint = {
  date: string;
  close: number;
  portfolio_value: number;
  benchmark_value: number;
  drawdown: number;
  signal: number;
  trade_signal: number;
};

type Trade = {
  date: string;
  close: number;
  trade_signal: number;
  shares: number;
  cash: number;
  portfolio_value: number;
  realized_pnl: number;
};

type BacktestResponse = {
  ticker: string;
  strategy: Strategy;
  metrics: Record<string, number>;
  equity_curve: EquityPoint[];
  trades: Trade[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://alphanexus-api.onrender.com";

const today = new Date();
const oneYearAgo = new Date(today);
oneYearAgo.setFullYear(today.getFullYear() - 1);

const STRATEGY_LABELS: Record<Strategy, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_breakout: "Bollinger Breakout",
};

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function percent(value?: number) {
  return `${((value ?? 0) * 100).toFixed(2)}%`;
}

function dollars(value?: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

function csvDownload(rows: Record<string, string | number>[]) {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => JSON.stringify(row[header] ?? "")).join(",")),
  ].join("\n");
  return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
}

function metricCards(result: BacktestResponse | null) {
  return [
    { label: "Ending Equity", value: dollars(result?.metrics.ending_equity) },
    { label: "Strategy Return", value: percent(result?.metrics.total_return) },
    { label: "Benchmark", value: percent(result?.metrics.benchmark_return) },
    { label: "Max Drawdown", value: percent(result?.metrics.max_drawdown) },
    { label: "Sharpe Ratio", value: (result?.metrics.sharpe_ratio ?? 0).toFixed(2) },
    { label: "Win Rate", value: percent(result?.metrics.win_rate) },
  ];
}

export default function Page() {
  const [ticker, setTicker] = useState("AAPL");
  const [strategy, setStrategy] = useState<Strategy>("sma_crossover");
  const [interval, setInterval] = useState<"1d" | "1h">("1d");
  const [start, setStart] = useState(isoDate(oneYearAgo));
  const [end, setEnd] = useState(isoDate(today));
  const [startingCash, setStartingCash] = useState(10000);
  const [smaRange, setSmaRange] = useState([17, 50]);
  const [rsiWindow, setRsiWindow] = useState(14);
  const [oversold, setOversold] = useState(30);
  const [overbought, setOverbought] = useState(70);
  const [bandWindow, setBandWindow] = useState(20);
  const [bandStd, setBandStd] = useState(2);
  const [feeBps, setFeeBps] = useState(5);
  const [slippageBps, setSlippageBps] = useState(5);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const latestTrades = useMemo(() => result?.trades.slice(-10).reverse() ?? [], [result]);
  const chartData = useMemo(
    () =>
      result?.equity_curve.map((point) => ({
        ...point,
        dateLabel: new Date(point.date).toLocaleDateString(),
        drawdownPercent: point.drawdown * 100,
      })) ?? [],
    [result],
  );

  const underperformed =
    result && result.metrics.total_return < result.metrics.benchmark_return
      ? result.metrics.benchmark_return - result.metrics.total_return
      : 0;

  const badges = [
    ticker,
    STRATEGY_LABELS[strategy],
    `${interval} bars`,
    `${feeBps} bps fee`,
    `${slippageBps} bps slippage`,
    `${result?.metrics.trade_count ?? 0} trades`,
  ];

  async function runBacktest() {
    setLoading(true);
    setError("");

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(`${API_BASE}/backtests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          ticker,
          strategy,
          start,
          end,
          interval,
          starting_cash: startingCash,
          fee_bps: feeBps,
          slippage_bps: slippageBps,
          allocation: 1,
          fast_window: smaRange[0],
          slow_window: smaRange[1],
          rsi_window: rsiWindow,
          oversold,
          overbought,
          band_window: bandWindow,
          band_std: bandStd,
        }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(body?.detail ?? `Backtest failed with status ${response.status}.`);
        return;
      }

      setResult(await response.json());
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === "AbortError"
          ? "The API request timed out. Render may be waking up; try again in a moment."
          : "Could not reach the API. Check NEXT_PUBLIC_API_BASE_URL and Render CORS settings.";
      setError(message);
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  }

  const latestTradeRows = latestTrades.map((trade) => ({
    date: new Date(trade.date).toLocaleDateString(),
    side: trade.trade_signal > 0 ? "Buy" : "Sell",
    price: dollars(trade.close),
    shares: trade.shares.toFixed(4),
    portfolio: dollars(trade.portfolio_value),
    realized_pnl: dollars(trade.realized_pnl),
  }));

  const tradeExport =
    result?.trades.map((trade) => ({
      date: trade.date,
      side: trade.trade_signal > 0 ? "Buy" : "Sell",
      price: trade.close,
      shares: trade.shares,
      portfolio_value: trade.portfolio_value,
      realized_pnl: trade.realized_pnl,
    })) ?? [];

  const equityExport =
    result?.equity_curve.map((point) => ({
      date: point.date,
      close: point.close,
      portfolio_value: point.portfolio_value,
      benchmark_value: point.benchmark_value,
      drawdown: point.drawdown,
      signal: point.signal,
      trade_signal: point.trade_signal,
    })) ?? [];

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span>Research Workbench</span>
          <h1>AlphaNexus</h1>
          <p>Configure market data, strategy rules, and cost assumptions.</p>
        </div>

        <section className="section">
          <h2>Market</h2>
          <div className="field">
            <label htmlFor="ticker">Ticker</label>
            <input id="ticker" value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} />
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="start">Start</label>
              <input id="start" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="end">End</label>
              <input id="end" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="interval">Interval</label>
            <select id="interval" value={interval} onChange={(event) => setInterval(event.target.value as "1d" | "1h")}>
              <option value="1d">1d</option>
              <option value="1h">1h</option>
            </select>
          </div>
        </section>

        <section className="section">
          <h2>Strategy</h2>
          <div className="field">
            <label htmlFor="strategy">Strategy</label>
            <select id="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value as Strategy)}>
              <option value="sma_crossover">SMA Crossover</option>
              <option value="rsi_mean_reversion">RSI Mean Reversion</option>
              <option value="bollinger_breakout">Bollinger Breakout</option>
            </select>
          </div>

          {strategy === "sma_crossover" ? (
            <div className="field">
              <div className="range-label">
                <label>SMA Windows</label>
                <span>
                  {smaRange[0]} / {smaRange[1]} days
                </span>
              </div>
              <Slider.Root
                className="range-slider"
                min={5}
                max={200}
                minStepsBetweenThumbs={5}
                step={1}
                value={smaRange}
                onValueChange={setSmaRange}
              >
                <Slider.Track className="range-track">
                  <Slider.Range className="range-fill" />
                </Slider.Track>
                <Slider.Thumb className="range-thumb" aria-label="Fast SMA window" />
                <Slider.Thumb className="range-thumb" aria-label="Slow SMA window" />
              </Slider.Root>
            </div>
          ) : null}

          {strategy === "rsi_mean_reversion" ? (
            <>
              <div className="field">
                <label htmlFor="rsiWindow">RSI Window</label>
                <input id="rsiWindow" type="number" value={rsiWindow} onChange={(event) => setRsiWindow(Number(event.target.value))} />
              </div>
              <div className="field-grid">
                <div className="field">
                  <label htmlFor="oversold">Oversold</label>
                  <input id="oversold" type="number" value={oversold} onChange={(event) => setOversold(Number(event.target.value))} />
                </div>
                <div className="field">
                  <label htmlFor="overbought">Overbought</label>
                  <input id="overbought" type="number" value={overbought} onChange={(event) => setOverbought(Number(event.target.value))} />
                </div>
              </div>
            </>
          ) : null}

          {strategy === "bollinger_breakout" ? (
            <div className="field-grid">
              <div className="field">
                <label htmlFor="bandWindow">Band Window</label>
                <input id="bandWindow" type="number" value={bandWindow} onChange={(event) => setBandWindow(Number(event.target.value))} />
              </div>
              <div className="field">
                <label htmlFor="bandStd">Band Width</label>
                <input id="bandStd" type="number" step="0.1" value={bandStd} onChange={(event) => setBandStd(Number(event.target.value))} />
              </div>
            </div>
          ) : null}
        </section>

        <section className="section">
          <h2>Portfolio</h2>
          <div className="field">
            <label htmlFor="cash">Starting Cash</label>
            <input id="cash" type="number" value={startingCash} onChange={(event) => setStartingCash(Number(event.target.value))} />
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="fees">Fee bps</label>
              <input id="fees" type="number" min="0" step="1" value={feeBps} onChange={(event) => setFeeBps(Number(event.target.value))} />
            </div>
            <div className="field">
              <label htmlFor="slippage">Slip bps</label>
              <input
                id="slippage"
                type="number"
                min="0"
                step="1"
                value={slippageBps}
                onChange={(event) => setSlippageBps(Number(event.target.value))}
              />
            </div>
          </div>
        </section>
      </aside>

      <section className="content">
        <div className="topbar">
          <div>
            <p className="eyebrow">Strategy research</p>
            <h2>Performance Dashboard</h2>
            <p className="muted">Compare a configurable strategy against buy-and-hold with explicit cost assumptions.</p>
          </div>
          <div className="top-actions">
            <div className="status">
              {error ? <span className="error">{error}</span> : result ? `${result.ticker} result loaded` : "Ready to run"}
            </div>
            <button className="primary-button" onClick={runBacktest} disabled={loading}>
              {loading ? "Running..." : "Run Backtest"}
            </button>
          </div>
        </div>

        <div className="badge-row">
          {badges.map((badge) => (
            <span className="badge" key={badge}>
              {badge}
            </span>
          ))}
        </div>

        {underperformed ? (
          <div className="alert-banner">
            Strategy underperformed buy-and-hold by {percent(underperformed)} over the selected period.
          </div>
        ) : null}

        <div className="metrics">
          {metricCards(result).map((metric) => (
            <div className="metric" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>

        <Tabs.Root className="tabs-root" defaultValue="performance">
          <Tabs.List className="tabs-list" aria-label="Dashboard sections">
            <Tabs.Trigger className="tabs-trigger" value="performance">
              Performance
            </Tabs.Trigger>
            <Tabs.Trigger className="tabs-trigger" value="trades">
              Trades
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
                  {chartData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke="#273142" strokeDasharray="3 3" />
                        <XAxis dataKey="dateLabel" tick={{ fill: "#9aa4b2", fontSize: 12 }} minTickGap={32} />
                        <YAxis tick={{ fill: "#9aa4b2", fontSize: 12 }} tickFormatter={(value) => dollars(Number(value))} width={86} />
                        <Tooltip
                          contentStyle={{ background: "#151b24", border: "1px solid #273142", borderRadius: 8 }}
                          formatter={(value) => dollars(Number(value ?? 0))}
                        />
                        <Legend />
                        <Line type="monotone" dataKey="portfolio_value" name="Strategy" stroke="#2f80ed" strokeWidth={3} dot={false} />
                        <Line type="monotone" dataKey="benchmark_value" name="Buy and hold" stroke="#9aa4b2" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="empty-chart">Run a backtest to render the equity curve.</div>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h3>Drawdown</h3>
                  <span className="muted">Peak-to-trough risk</span>
                </div>
                <div className="chart small">
                  {chartData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke="#273142" strokeDasharray="3 3" />
                        <XAxis dataKey="dateLabel" tick={{ fill: "#9aa4b2", fontSize: 12 }} minTickGap={32} />
                        <YAxis tick={{ fill: "#9aa4b2", fontSize: 12 }} tickFormatter={(value) => `${Number(value).toFixed(0)}%`} width={52} />
                        <Tooltip
                          contentStyle={{ background: "#151b24", border: "1px solid #273142", borderRadius: 8 }}
                          formatter={(value) => `${Number(value ?? 0).toFixed(2)}%`}
                        />
                        <Area type="monotone" dataKey="drawdownPercent" name="Drawdown" stroke="#ef4444" fill="#ef444433" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="empty-chart">Drawdown appears after a completed run.</div>
                  )}
                </div>
              </section>
            </div>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="trades">
            <section className="panel">
              <div className="panel-header">
                <h3>Recent Trades</h3>
                <span className="muted">Executed entries and exits</span>
              </div>
              <DataTable rows={latestTradeRows} emptyMessage="No trades to display yet." />
            </section>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="assumptions">
            <section className="panel assumptions">
              <div>
                <h3>Execution Model</h3>
                <p>The simulator is long-only and moves between cash and one position. Fees and slippage are applied when trades execute.</p>
              </div>
              <div>
                <h3>Active Parameters</h3>
                <ul>
                  <li>Ticker: {ticker}</li>
                  <li>Strategy: {STRATEGY_LABELS[strategy]}</li>
                  <li>Date range: {start} to {end}</li>
                  <li>Starting cash: {dollars(startingCash)}</li>
                  <li>Costs: {feeBps} bps fee, {slippageBps} bps slippage</li>
                </ul>
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content className="tabs-content" value="exports">
            <section className="panel export-panel">
              <h3>Export Results</h3>
              <p className="muted">Download the latest result for documentation or follow-up analysis.</p>
              <div className="export-actions">
                <a className="secondary-button" href={csvDownload(equityExport)} download={`${ticker.toLowerCase()}_equity_curve.csv`}>
                  Equity Curve CSV
                </a>
                <a className="secondary-button" href={csvDownload(tradeExport)} download={`${ticker.toLowerCase()}_trades.csv`}>
                  Trade Ledger CSV
                </a>
              </div>
            </section>
          </Tabs.Content>
        </Tabs.Root>
      </section>
    </main>
  );
}

function DataTable({ rows, emptyMessage }: { rows: Record<string, string | number>[]; emptyMessage: string }) {
  if (rows.length === 0) {
    return <div className="empty-table">{emptyMessage}</div>;
  }

  const headers = Object.keys(rows[0]);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => (
                <td key={header}>{row[header]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
