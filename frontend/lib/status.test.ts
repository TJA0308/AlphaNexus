import { describe, expect, it } from "vitest";

import { loadingMessage } from "./status";

describe("loadingMessage", () => {
  it("describes the first-load example run", () => {
    expect(loadingMessage({ hasResult: false, slow: false })).toBe("Loading an example AAPL backtest…");
  });

  it("describes a user-started run once a result is on screen", () => {
    expect(loadingMessage({ hasResult: true, slow: false })).toBe("Running backtest…");
  });

  it("explains a slow request as a cold start, whatever started it", () => {
    for (const hasResult of [false, true]) {
      expect(loadingMessage({ hasResult, slow: true })).toMatch(/waking up/);
    }
  });
});
