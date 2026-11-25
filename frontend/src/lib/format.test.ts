import { afterEach, describe, expect, it, vi } from "vitest";
import { formatDate, formatSalary, isoToLocalDate, localDateToIso, relativeTime } from "./format";

describe("formatSalary", () => {
  it("formatiert Spannen, Unter- und Obergrenzen", () => {
    expect(formatSalary(50000, 65000, "EUR")).toMatch(/^50\.000\s€ – 65\.000\s€$/);
    expect(formatSalary(50000, null, "EUR")).toMatch(/^ab 50\.000/);
    expect(formatSalary(null, 65000, "EUR")).toMatch(/^bis 65\.000/);
    expect(formatSalary(null, null, "EUR")).toBeNull();
  });
});

describe("Datumsfunktionen", () => {
  afterEach(() => vi.useRealTimers());

  it("zeigt relative Zeiten auf Deutsch", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-25T12:00:00Z"));
    expect(relativeTime("2026-11-25T11:59:30Z")).toBe("gerade eben");
    expect(relativeTime("2026-11-24T12:00:00Z")).toBe("gestern");
    expect(relativeTime("2026-11-25T09:00:00Z")).toBe("vor 3 Stunden");
  });

  it("wandelt Datumsfelder verlustfrei hin und zurück", () => {
    const iso = localDateToIso("2026-12-01");
    expect(iso).not.toBeNull();
    expect(isoToLocalDate(iso)).toBe("2026-12-01");
    expect(localDateToIso("")).toBeNull();
    expect(formatDate(null)).toBe("–");
  });
});
