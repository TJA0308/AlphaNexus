import type { BarInterval } from "./types";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function percent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function dollars(value: number) {
  return currency.format(value);
}

// Hourly bars need the time as well, or every bar in a session shares a label.
export function barLabel(date: string, interval: BarInterval) {
  const parsed = new Date(date);
  return interval === "1h"
    ? parsed.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : parsed.toLocaleDateString("en-US");
}

// SQLite's CURRENT_TIMESTAMP is UTC without a zone marker, so mark it as UTC
// before parsing or the browser would read it as local time.
export function sqliteTimestampLabel(timestamp: string) {
  return new Date(`${timestamp.replace(" ", "T")}Z`).toLocaleString("en-US");
}

// Every field is quoted, and embedded quotes are doubled, as RFC 4180 requires.
// JSON.stringify is not a substitute: it escapes quotes with a backslash, which
// spreadsheet tools do not understand.
function csvField(value: string | number) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

export function toCsv(rows: Record<string, string | number>[]) {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  return [
    headers.map(csvField).join(","),
    ...rows.map((row) => headers.map((header) => csvField(row[header] ?? "")).join(",")),
  ].join("\n");
}
