import type { SearchHit } from "../api/types";
import { sameTag, splitHashtags } from "./tags";

/** Hashtags aller Treffer mit Anzahl, häufigste zuerst (bei Gleichstand alphabetisch). */
export function tagCounts(hits: SearchHit[], limit = 24): { name: string; count: number }[] {
  const counts = new Map<string, { name: string; count: number }>();
  for (const h of hits) {
    for (const t of h.tags ?? []) {
      const key = t.toLocaleLowerCase("de");
      const cur = counts.get(key);
      if (cur) cur.count += 1;
      else counts.set(key, { name: t, count: 1 });
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "de")).slice(0, limit);
}

/** Alle gewählten Hashtags müssen passen (UND), wie in der Liste „Meine Stellen“. */
export function filterByTags(hits: SearchHit[], selected: string[]): SearchHit[] {
  if (selected.length === 0) return hits;
  return hits.filter((h) => selected.every((s) => (h.tags ?? []).some((t) => sameTag(t, s))));
}

/**
 * Suchbegriff für die Portale: "#python Data Scientist" -> "Data Scientist python".
 * Portale kennen keine Hashtags, deshalb werden sie zu normalen Suchwörtern
 * ("machine-learning" -> "machine learning").
 */
export function portalQuery(input: string): string {
  const { text, tags } = splitHashtags(input);
  return [text, ...tags.map((t) => t.replace(/[-_]+/g, " "))].filter(Boolean).join(" ");
}
