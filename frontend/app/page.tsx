"use client";

import { FormEvent, useMemo, useState } from "react";

type Strategy = "sma_crossover" | "rsi_mean_reversion" | "bollinger_breakout";

type EquityPoint = {
  date: string;
  close: number;
  portfolio_value: number;
  benchmark_value: number;
  drawdown: number;
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const today = new Date();
const oneYearAgo = new Date(today);
oneYearAgo.setFullYear(today.getFullYear() - 1);

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
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

function linePath(points: number[], width: number, height: number, min: number, max: number) {
  if (points.length === 0) return "";
  const range = max - min || 1;

  return points
    .map((point, index) => {
      const x = points.length === 1 ? 0 : (index / (points.length - 1)) * width;
      const y = height - ((point - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function LineChart({
  data,
  series,
  height = 320,
}: {
  data: EquityPoint[];
  series: { key: keyof EquityPoint; color: string; label: string }[];
  height?: number;
}) {
  const width = 900;
  const values = series.flatMap((item) => data.map((point) => Number(point[item.key])));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const paths = series.map((item) => ({
    ...item,
    path: linePath(
      data.map((point) => Number(point[item.key])),
      width,
      height,
      min,
      max,
    ),
  }));

  return (
    <svg className={height < 300 ? "chart small" : "chart"} viewBox={`0 0 ${width} ${height}`} role="img">
      <line x1="0" x2={width} y1={height - 1} y2={height - 1} stroke="#273142" />
      {paths.map((item) => (
        <path key={String(item.key)} className="chart-line" d={item.path} stroke={item.color} />
      ))}
    </svg>
  );
}

export default function Page() {
  const [ticker, setTicker] = useState("AAPL");
  const [strategy, setStrategy] = useState<Strategy>("sma_crossover");
  const [start, setStart] = useState(isoDate(oneYearAgo));
  const [end, setEnd] = useState(isoDate(today));
  const [startingCash, setStartingCash] = useState(10000);
  const [feeBps, setFeeBps] = useState(5);
  const [slippageBps, setSlippageBps] = useState(5);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const latestTrades = useMemo(() => result?.trades.slice(-8).reverse() ?? [], [result]);

  async function runBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    const response = await fetch(`${API_BASE}/backtests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker,
        strategy,
        start,
        end,
        interval: "1d",
        starting_cash: startingCash,
        fee_bps: feeBps,
        slippage_bps: slippageBps,
        allocation: 1,
      }),
    });

    setLoading(false);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setError(body?.detail ?? "Backtest failed.");
      return;
    }
    setResult(await response.json());
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>AlphaNexus</h1>
          <p>Backtesting lab for strategy research and portfolio risk review.</p>
        </div>

        <form onSubmit={runBacktest}>
          <section className="section">
            <h2>Market</h2>
            <div className="field">
              <label htmlFor="ticker">Ticker</label>
              <input id="ticker" value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} />
            </div>
            <div className="field">
              <label htmlFor="strategy">Strategy</label>
              <select id="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value as Strategy)}>
                <option value="sma_crossover">SMA Crossover</option>
                <option value="rsi_mean_reversion">RSI Mean Reversion</option>
                <option value="bollinger_breakout">Bollinger Breakout</option>
              </select>
            </div>
          </section>

          <section className="section">
            <h2>Backtest</h2>
            <div className="field">
              <label htmlFor="start">Start date</label>
              <input id="start" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="end">End date</label>
              <input id="end" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="cash">Starting cash</label>
              <input
                id="cash"
                type="number"
                value={startingCash}
                onChange={(event) => setStartingCash(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label htmlFor="fees">Fees, bps</label>
              <input id="fees" type="number" value={feeBps} onChange={(event) => setFeeBps(Number(event.target.value))} />
            </div>
            <div className="field">
              <label htmlFor="slippage">Slippage, bps</label>
              <input
                id="slippage"
                type="number"
                value={slippageBps}
                onChange={(event) => setSlippageBps(Number(event.target.value))}
              />
            </div>
          </section>

          <button className="primary-button" disabled={loading}>
            {loading ? "Running..." : "Run backtest"}
          </button>
        </form>
      </aside>

      <section className="content">
        <div className="topbar">
          <div>
            <h2>Strategy Performance</h2>
            <p className="muted">Compare strategy equity, benchmark return, drawdown, and executed trades.</p>
          </div>
          <div className="status">
            {error ? <span className="error">{error}</span> : result ? `${result.ticker} loaded` : "Waiting for run"}
          </div>
        </div>

        <div className="metrics">
          <div className="metric">
            <span>Ending equity</span>
            <strong>{dollars(result?.metrics.ending_equity)}</strong>
          </div>
          <div className="metric">
            <span>Total return</span>
            <strong>{percent(result?.metrics.total_return)}</strong>
          </div>
          <div className="metric">
            <span>Benchmark</span>
            <strong>{percent(result?.metrics.benchmark_return)}</strong>
          </div>
          <div className="metric">
            <span>Max drawdown</span>
            <strong>{percent(result?.metrics.max_drawdown)}</strong>
          </div>
          <div className="metric">
            <span>Sharpe</span>
            <strong>{(result?.metrics.sharpe_ratio ?? 0).toFixed(2)}</strong>
          </div>
          <div className="metric">
            <span>Trades</span>
            <strong>{result?.metrics.trade_count ?? 0}</strong>
          </div>
        </div>

        <div className="grid">
          <section className="panel">
            <div className="panel-header">
              <h3>Equity Curve</h3>
              <span className="muted">Strategy vs. buy-and-hold</span>
            </div>
            <LineChart
              data={result?.equity_curve ?? []}
              series={[
                { key: "portfolio_value", color: "#2f80ed", label: "Strategy" },
                { key: "benchmark_value", color: "#9aa4b2", label: "Benchmark" },
              ]}
            />
          </section>

          <section className="panel">
            <div className="panel-header">
              <h3>Drawdown</h3>
              <span className="muted">Peak-to-trough risk</span>
            </div>
            <LineChart data={result?.equity_curve ?? []} series={[{ key: "drawdown", color: "#ef4444", label: "Drawdown" }]} height={240} />
          </section>
        </div>

        <section className="panel" style={{ marginTop: 14 }}>
          <div className="panel-header">
            <h3>Recent Trades</h3>
            <span className="muted">Executed entries and exits</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Side</th>
                  <th>Price</th>
                  <th>Shares</th>
                  <th>Portfolio</th>
                  <th>Realized PnL</th>
                </tr>
              </thead>
              <tbody>
                {latestTrades.map((trade) => (
                  <tr key={`${trade.date}-${trade.trade_signal}`}>
                    <td>{new Date(trade.date).toLocaleDateString()}</td>
                    <td className={trade.trade_signal > 0 ? "positive" : "negative"}>{trade.trade_signal > 0 ? "Buy" : "Sell"}</td>
                    <td>{dollars(trade.close)}</td>
                    <td>{trade.shares.toFixed(4)}</td>
                    <td>{dollars(trade.portfolio_value)}</td>
                    <td className={trade.realized_pnl >= 0 ? "positive" : "negative"}>{dollars(trade.realized_pnl)}</td>
                  </tr>
                ))}
                {latestTrades.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="muted">
                      No trades to display yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}
