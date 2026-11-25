import { describe, expect, it } from "vitest";

import type { Stats } from "../api/types";
import { logbook, MAX_BUOYS, MAX_PENNANTS, voyageFrom, windLevel } from "./voyage";

function stats(over: Partial<Stats> & { status?: Record<string, number> } = {}): Stats {
  const { status = {}, ...rest } = over;
  return {
    total: 0,
    active: 0,
    by_status: Object.entries(status).map(([key, count]) => ({ key, count })),
    by_source: [],
    response_rate: null,
    activity_7d: 0,
    last_activity_at: null,
    ...rest,
  };
}

describe("Seefahrt aus Kennzahlen", () => {
  it("leitet den Wind aus der Aktivität der letzten 7 Tage ab", () => {
    expect([0, 1, 3, 4, 9, 10, 50].map(windLevel)).toEqual([0, 1, 1, 2, 2, 3, 3]);
  });

  it("zählt Wimpel, Bojen, Leuchtfeuer und Land und begrenzt die Zeichnung", () => {
    const v = voyageFrom(stats({ active: 12, activity_7d: 5, status: { interview: 7, offer: 1, accepted: 1 } }));
    expect(v).toMatchObject({ wind: 2, windLabel: "frische Brise", pennants: MAX_PENNANTS, active: 12 });
    expect(v).toMatchObject({ buoys: MAX_BUOYS, interviews: 7, offers: 1, accepted: 1 });
  });

  it("schreibt ein Logbuch nur mit vorhandenen Einträgen", () => {
    expect(logbook(voyageFrom(stats())).map((e) => e.label)).toEqual(["Flaute: 0 Schritte in 7 Tagen"]);
    const full = logbook(voyageFrom(stats({ active: 3, activity_7d: 1, status: { interview: 1, offer: 2, accepted: 1 } })));
    expect(full.map((e) => e.label)).toEqual([
      "Leichte Brise: 1 Schritt in 7 Tagen",
      "3 Wimpel = laufende Bewerbungen",
      "1 Boje = Gespräch",
      "Leuchtfeuer: 2 Angebote",
      "Land in Sicht: Zusage!",
    ]);
  });
});
