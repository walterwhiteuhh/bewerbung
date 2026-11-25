import { describe, expect, it } from "vitest";
import { hit } from "../test/fixtures";
import { sortHits } from "./sortHits";

const hits = [
  hit(1, { match_score: 0.2, distance_km: 40, age_days: 3 }),
  hit(2, { match_score: 0.9, distance_km: null, age_days: 10 }),
  hit(3, null),
  hit(4, { match_score: 0.9, distance_km: 5, age_days: 1 }),
];
const ranks = (xs: typeof hits) => xs.map((h) => h.rank);

describe("sortHits", () => {
  it("lässt die Portal-Reihenfolge unverändert", () => {
    expect(ranks(sortHits(hits, "rank"))).toEqual([1, 2, 3, 4]);
  });

  it("sortiert nach Passung absteigend, Gleichstand nach Rang, fehlende Werte ans Ende", () => {
    expect(ranks(sortHits(hits, "match"))).toEqual([2, 4, 1, 3]);
  });

  it("sortiert nach Entfernung aufsteigend", () => {
    expect(ranks(sortHits(hits, "distance"))).toEqual([4, 1, 2, 3]);
  });

  it("sortiert nach Alter und verändert die Eingabe nicht", () => {
    const before = ranks(hits);
    expect(ranks(sortHits(hits, "fresh"))).toEqual([4, 1, 2, 3]);
    expect(ranks(hits)).toEqual(before);
  });
});
