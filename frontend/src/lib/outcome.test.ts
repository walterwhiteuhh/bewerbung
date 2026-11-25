import { describe, expect, it } from "vitest";
import { asksSalary, parseSalary, reasonsFor } from "./outcome";

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
});
