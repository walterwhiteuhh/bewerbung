import { describe, expect, it } from "vitest";

import type { SearchRunSummary } from "../api/types";
import { groupRuns, olderThan, periodRange, rangeParams } from "./runHistory";

const NOW = new Date(2026, 10, 25, 12, 0);
const run = (id: number, d: Date): SearchRunSummary =>
  ({ id, query: `q${id}`, started_at: d.toISOString() }) as SearchRunSummary;

describe("runHistory", () => {
  it("gruppiert nach Tag mit Heute/Gestern", () => {
    const groups = groupRuns(
      [run(1, new Date(2026, 10, 25, 9)), run(2, new Date(2026, 10, 25, 8)), run(3, new Date(2026, 10, 24, 23)), run(4, new Date(2026, 10, 1))],
      NOW,
    );
    expect(groups.map((g) => [g.label, g.runs.length])).toEqual([["Heute", 2], ["Gestern", 1], [groups[2]!.label, 1]]);
    expect(groups[2]!.label).toMatch(/01\.11\.2026/);
    expect(groups[0]!.range.to.getTime() - groups[0]!.range.from.getTime()).toBe(86_400_000);
  });

  it("berechnet Zeiträume", () => {
    expect(periodRange("all", NOW)).toEqual({});
    expect(periodRange("today", NOW).from).toEqual(new Date(2026, 10, 25));
    expect(periodRange("7d", NOW).from).toEqual(new Date(2026, 10, 19));
    expect(olderThan(7, NOW).to).toEqual(new Date(2026, 10, 19));
  });

  it("macht ISO-Parameter für die API", () => {
    expect(rangeParams({})).toEqual({ from: undefined, to: undefined });
    expect(rangeParams({ to: new Date(Date.UTC(2026, 0, 1)) }).to).toBe("2026-01-01T00:00:00.000Z");
  });
});
