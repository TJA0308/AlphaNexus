import type { BacktestRequest, BacktestResponse, RunSummary } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://alphanexus-api.onrender.com";

// Render's free tier can take ~30s to wake, so anything shorter would time out
// the first request after an idle period.
const REQUEST_TIMEOUT_MS = 45_000;

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

// FastAPI returns `detail` as a string for errors we raise ourselves, but as a
// list of issues for request-validation failures (422). Rendering that list
// directly would crash React, so both shapes are reduced to one message.
export function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    return (detail as ValidationIssue[])
      .map((issue) => {
        const field = issue.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg}` : issue.msg;
      })
      .filter(Boolean)
      .join("; ");
  }

  return `Request failed with status ${status}.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The API request timed out. The server may be waking up; try again in a moment.");
    }
    throw new Error("Could not reach the API. Check NEXT_PUBLIC_API_BASE_URL and the server's CORS settings.");
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(errorMessage(body?.detail, response.status));
  }

  return response.json() as Promise<T>;
}

// `save: false` runs the backtest without recording it in the shared history.
export function runBacktest(body: BacktestRequest, { save = true }: { save?: boolean } = {}) {
  return request<BacktestResponse>(save ? "/backtests" : "/backtests?save=false", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchRuns(limit = 20) {
  return request<RunSummary[]>(`/backtests?limit=${limit}`);
}
