"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { dollars } from "../lib/format";

export type ChartPoint = {
  label: string;
  portfolio_value: number;
  benchmark_value: number;
  drawdownPercent: number;
};

const axisTick = { fill: "#9aa4b2", fontSize: 12 };
const tooltipStyle = { background: "#151b24", border: "1px solid #273142", borderRadius: 8 };

// ResponsiveContainer starts at -1 x -1 until it has measured its box, and
// logs a console warning for that first render. Any positive starting size
// avoids it; the real size replaces this immediately.
const initialDimension = { width: 1, height: 1 };

export function EquityChart({ data }: { data: ChartPoint[] }) {
  if (!data.length) return <div className="empty-chart">Run a backtest to render the equity curve.</div>;

  return (
    <ResponsiveContainer width="100%" height="100%" initialDimension={initialDimension}>
      <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#273142" strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={axisTick} minTickGap={32} />
        <YAxis tick={axisTick} tickFormatter={(value) => dollars(Number(value))} width={86} domain={["auto", "auto"]} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => dollars(Number(value ?? 0))} />
        <Legend />
        <Line type="monotone" dataKey="portfolio_value" name="Strategy" stroke="#2f80ed" strokeWidth={3} dot={false} />
        <Line type="monotone" dataKey="benchmark_value" name="Buy and hold" stroke="#9aa4b2" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// An <Area> only renders inside an AreaChart (or ComposedChart). It used to
// sit inside a LineChart, which drew the axes and silently dropped the series.
export function DrawdownChart({ data }: { data: ChartPoint[] }) {
  if (!data.length) return <div className="empty-chart">Drawdown appears after a completed run.</div>;

  return (
    <ResponsiveContainer width="100%" height="100%" initialDimension={initialDimension}>
      <AreaChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#273142" strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={axisTick} minTickGap={32} />
        <YAxis tick={axisTick} tickFormatter={(value) => `${Number(value).toFixed(0)}%`} width={52} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => `${Number(value ?? 0).toFixed(2)}%`} />
        <Area type="monotone" dataKey="drawdownPercent" name="Drawdown" stroke="#ef4444" fill="#ef444433" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
