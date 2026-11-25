import { describe, expect, it } from "vitest";
import type { Stats } from "../api/types";
import { asksSalary, outcomeSummary, parseSalary, reasonsFor } from "./outcome";

describe("outcome", () => {
  it("bietet Gründe nur bei Absage und Rückzug", () => {
    expect(reasonsFor("rejected")).toContain("rejected_interview");
    expect(reasonsFor("withdrawn")).toContain("better_offer");
    expect(reasonsFor("applied")).toEqual([]);
    expect(reasonsFor("offer")).toEqual([]);
  });

  it("fragt das Gehalt nur bei Angebot und Zusage", () => {
    expect(asksSalary("offer")).toBe(true);
    expect(asksSalary("accepted")).toBe(true);
    expect(asksSalary("rejected")).toBe(false);
  });

  it("liest Gehälter tolerant", () => {
    expect(parseSalary("65.000")).toBe(65000);
    expect(parseSalary("65 000")).toBe(65000);
    expect(parseSalary("65000")).toBe(65000);
    expect(parseSalary("")).toBeUndefined();
    expect(parseSalary("abc")).toBeUndefined();
    expect(parseSalary("0")).toBeUndefined();
    expect(parseSalary("99999999")).toBeUndefined();
  });

  it("fasst Gründe und Gehälter zusammen", () => {
    const stats = {
      by_reason: [{ key: "salary_mismatch", count: 2 }, { key: "unbekannt", count: 1 }],
      offer_salaries: [{ currency: "EUR", count: 2, min: 60000, median: 70000, max: 80000 }],
    } as Stats;
    const s = outcomeSummary(stats);
    expect(s.reasons.map((r) => r.label)).toEqual(["Gehalt passt nicht", "unbekannt"]);
    expect(s.salary).toMatch(/Ø 70\.000\s€ \(60\.000\s€ – 80\.000\s€\), 2 Angebote/);
    expect(outcomeSummary(undefined)).toEqual({ reasons: [], salary: null });
  });
});
