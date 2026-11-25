import type { PrimaryCvPeriod, ProfileVersion } from "../api/types";
import { formatDate } from "./format";
import { PROFILE_FIELD_LABEL } from "./labels";

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** "Skills, Kurzprofil geändert" bzw. "Erste Fassung" für den ältesten Stand. */
export function describeVersion(v: ProfileVersion): string {
  if (v.is_first) return "Erste Fassung";
  const names = v.changed_fields.map((f) => PROFILE_FIELD_LABEL[f] ?? f);
  return names.length ? `${names.join(", ")} geändert` : "Ohne inhaltliche Änderung";
}

export const describeSkills = (v: ProfileVersion): string | null => {
  const parts = [
    ...v.skills_added.map((s) => `+${s}`),
    ...v.skills_removed.map((s) => `−${s}`),
  ];
  return parts.length ? parts.join(" ") : null;
};

/** "03.11.2026 – heute" bzw. "03.11.2026 – 12.11.2026". */
export const describePeriod = (p: PrimaryCvPeriod): string =>
  `${formatDate(p.started_at)} – ${p.ended_at ? formatDate(p.ended_at) : "heute"}`;

export const usageText = (count: number): string =>
  count === 0 ? "keine Bewerbung damit" : `${plural(count, "Bewerbung", "Bewerbungen")} damit`;
