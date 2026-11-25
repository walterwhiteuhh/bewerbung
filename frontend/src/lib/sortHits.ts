import type { SearchHit } from "../api/types";

export type HitSort = "rank" | "match" | "distance" | "fresh";

/** Treffer nach Merkmal sortieren; Treffer ohne Wert kommen ans Ende, sonst gilt der Portal-Rang. */
export function sortHits(hits: SearchHit[], sort: HitSort): SearchHit[] {
  if (sort === "rank") return hits;
  const value = (h: SearchHit): number | null => {
    const f = h.features;
    if (!f) return null;
    if (sort === "match") return f.match_score === null ? null : -f.match_score;
    if (sort === "distance") return f.distance_km;
    return f.age_days;
  };
  return [...hits].sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    if (va === null || vb === null) return va === null ? (vb === null ? a.rank - b.rank : 1) : -1;
    return va - vb || a.rank - b.rank;
  });
}
