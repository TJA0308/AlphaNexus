import { describe, expect, it } from "vitest";

import { dollars, percent, sqliteTimestampLabel, toCsv } from "./format";

describe("percent", () => {
  it("formats a fraction as a two-decimal percentage", () => {
    expect(percent(0.1234)).toBe("12.34%");
    expect(percent(-0.05)).toBe("-5.00%");
    expect(percent(0)).toBe("0.00%");
  });
});

describe("dollars", () => {
  it("formats with a currency symbol, grouping, and cents", () => {
    expect(dollars(10426.06)).toBe("$10,426.06");
    expect(dollars(-12.5)).toBe("-$12.50");
  });
});

describe("toCsv", () => {
  it("returns an empty string for no rows", () => {
    expect(toCsv([])).toBe("");
  });

  it("writes a header row followed by one line per row", () => {
    const csv = toCsv([
      { date: "2024-01-02", price: 101.5 },
      { date: "2024-01-03", price: 99 },
    ]);
    expect(csv.split("\n")).toEqual(['"date","price"', '"2024-01-02","101.5"', '"2024-01-03","99"']);
  });

  it("doubles embedded quotes rather than backslash-escaping them", () => {
    // RFC 4180 escaping. Spreadsheets would misread a backslash escape.
    expect(toCsv([{ note: 'say "hi"' }])).toBe('"note"\n"say ""hi"""');
  });

  it("keeps commas and newlines inside a single quoted field", () => {
    const csv = toCsv([{ note: "a,b\nc" }]);
    expect(csv).toBe('"note"\n"a,b\nc"');
  });

  it("uses the first row's keys as the column order", () => {
    const csv = toCsv([{ b: 1, a: 2 }]);
    expect(csv.split("\n")[0]).toBe('"b","a"');
  });
});

describe("sqliteTimestampLabel", () => {
  it("treats SQLite's zone-less timestamp as UTC", () => {
    const label = sqliteTimestampLabel("2026-09-23 12:00:00");
    const expected = new Date(Date.UTC(2026, 8, 23, 12, 0, 0)).toLocaleString("en-US");
    expect(label).toBe(expected);
  });
});
