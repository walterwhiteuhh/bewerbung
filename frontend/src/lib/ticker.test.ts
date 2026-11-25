import { describe, expect, it } from "vitest";

import type { Stats } from "../api/types";
import { STATIC_ITEMS, liveItems, tickerItems } from "./ticker";

const stats = (over: Partial<Stats> = {}): Stats => ({
  total: 12,
  active: 5,
  by_status: [
    { key: "interview", count: 2 },
    { key: "offer", count: 1 },
  ],
  by_source: [],
  response_rate: null,
  activity_7d: 4,
  last_activity_at: null,
  by_reason: [],
  offer_salaries: [],
  ...over,
});

describe("ticker", () => {
  it("zeigt ohne Daten nur die Tipps", () => {
    expect(liveItems(undefined)).toEqual([]);
    expect(liveItems(stats({ total: 0 }))).toEqual([]);
    expect(tickerItems(undefined)).toEqual(STATIC_ITEMS);
  });

  it("bildet Live-Meldungen aus den Kennzahlen", () => {
    const texts = liveItems(stats()).map((i) => i.text);
    expect(texts[0]).toContain("frische Brise");
    expect(texts).toContain("12 Stellen an Bord, 5 im Rennen");
    expect(texts).toContain("2 Vorstellungsgespräche voraus");
    expect(texts.some((t) => t.includes("Leuchtfeuer"))).toBe(true);
  });

  it("mischt Live und Tipps ohne Verlust", () => {
    const items = tickerItems(stats());
    expect(items.length).toBe(STATIC_ITEMS.length + liveItems(stats()).length);
    expect(items[0]?.live).toBe(true);
    expect(items[1]?.live).toBeUndefined();
    expect(new Set(items.map((i) => i.id)).size).toBe(items.length);
  });
});
