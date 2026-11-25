import { describe, expect, it } from "vitest";

import type { SearchHit } from "../api/types";
import { filterByTags, portalQuery, tagCounts } from "./hitTags";

const hit = (id: number, tags: string[]) => ({ rank: id, is_new: false, listing: { id }, features: null, tags }) as unknown as SearchHit;
const hits = [hit(1, ["python", "remote"]), hit(2, ["Python", "sql"]), hit(3, ["sql"]), hit(4, [])];

describe("hitTags", () => {
  it("zählt Hashtags ohne Beachtung der Schreibweise", () => {
    expect(tagCounts(hits).map((t) => [t.name.toLowerCase(), t.count])).toEqual([
      ["python", 2],
      ["sql", 2],
      ["remote", 1],
    ]);
  });

  it("filtert mit UND", () => {
    expect(filterByTags(hits, []).length).toBe(4);
    expect(filterByTags(hits, ["python"]).map((h) => h.listing.id)).toEqual([1, 2]);
    expect(filterByTags(hits, ["python", "sql"]).map((h) => h.listing.id)).toEqual([2]);
    expect(filterByTags(hits, ["gibtsnicht"])).toEqual([]);
  });

  it("macht aus Hashtags im Suchfeld normale Suchwörter", () => {
    expect(portalQuery("Data Scientist #python")).toBe("Data Scientist python");
    expect(portalQuery("#machine-learning #remote")).toBe("machine learning remote");
    expect(portalQuery("kein tag")).toBe("kein tag");
  });
});
