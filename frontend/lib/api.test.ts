import { afterEach, describe, expect, it, vi } from "vitest";

import { errorMessage, fetchRuns, runBacktest } from "./api";
import type { BacktestRequest } from "./types";

const request: BacktestRequest = {
  ticker: "AAPL",
  start: "2024-01-01",
  end: "2024-12-31",
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

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("errorMessage", () => {
  it("passes a string detail through unchanged", () => {
    expect(errorMessage("start date must be before end date", 400)).toBe("start date must be before end date");
  });

  it("flattens a FastAPI validation list into one readable message", () => {
    const detail = [
      { loc: ["body", "oversold"], msg: "Input should be greater than 0" },
      { loc: ["body", "allocation"], msg: "Input should be less than or equal to 1" },
    ];
    expect(errorMessage(detail, 422)).toBe(
      "oversold: Input should be greater than 0; allocation: Input should be less than or equal to 1",
    );
  });

  it("falls back to the status code when there is no usable detail", () => {
    expect(errorMessage(undefined, 500)).toBe("Request failed with status 500.");
    expect(errorMessage([], 422)).toBe("Request failed with status 422.");
  });
});

describe("runBacktest", () => {
  it("POSTs the request as JSON and returns the parsed body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ticker: "AAPL" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await runBacktest(request);

    expect(result).toEqual({ ticker: "AAPL" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/backtests$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(request);
  });

  it("asks the API not to record the run when save is false", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await runBacktest(request, { save: false });

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/backtests\?save=false$/);
  });

  it("surfaces the API's detail message on a 400", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(400, { detail: "not enough data" })));

    await expect(runBacktest(request)).rejects.toThrow("not enough data");
  });

  it("does not crash on a 422 whose detail is a list", async () => {
    const detail = [{ loc: ["body", "oversold"], msg: "Input should be greater than 0" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(422, { detail })));

    await expect(runBacktest(request)).rejects.toThrow("oversold: Input should be greater than 0");
  });

  it("copes with an error response that is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad Gateway", { status: 502 })));

    await expect(runBacktest(request)).rejects.toThrow("Request failed with status 502.");
  });

  it("reports a timeout distinctly from a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
    await expect(runBacktest(request)).rejects.toThrow(/timed out/);

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(runBacktest(request)).rejects.toThrow(/Could not reach the API/);
  });
});

describe("fetchRuns", () => {
  it("requests the history with a limit", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchRuns(5)).resolves.toEqual([]);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/backtests\?limit=5$/);
  });
});
