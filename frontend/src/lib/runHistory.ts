import type { SearchRunSummary } from "../api/types";

export type Period = "all" | "today" | "7d" | "30d";
export type Range = { from?: Date; to?: Date };

export const startOfDay = (d: Date): Date => new Date(d.getFullYear(), d.getMonth(), d.getDate());
export const addDays = (d: Date, n: number): Date => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

/** Zeitraum eines Filters; `to` ist exklusiv (passt zur API: from <= Start < to). */
export function periodRange(period: Period, now = new Date()): Range {
  const today = startOfDay(now);
  if (period === "today") return { from: today };
  if (period === "7d") return { from: addDays(today, -6) };
  if (period === "30d") return { from: addDays(today, -29) };
  return {};
}

/** „Älter als n Tage“: alles vor dem Beginn von heute minus n Tagen. */
export const olderThan = (days: number, now = new Date()): Range => ({ to: addDays(startOfDay(now), -days + 1) });

export interface RunGroup {
  key: string;
  label: string;
  runs: SearchRunSummary[];
  range: Required<Range>;
}

const dayFmt = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });

/** Läufe nach lokalem Kalendertag gruppieren (Reihenfolge der Eingabe bleibt erhalten). */
export function groupRuns(runs: SearchRunSummary[], now = new Date()): RunGroup[] {
  const today = startOfDay(now);
  const groups = new Map<string, RunGroup>();
  for (const run of runs) {
    const day = startOfDay(new Date(run.started_at));
    const key = `${day.getFullYear()}-${day.getMonth() + 1}-${day.getDate()}`;
    let g = groups.get(key);
    if (!g) {
      const diff = Math.round((today.getTime() - day.getTime()) / 86_400_000);
      const label = diff === 0 ? "Heute" : diff === 1 ? "Gestern" : dayFmt.format(day);
      g = { key, label, runs: [], range: { from: day, to: addDays(day, 1) } };
      groups.set(key, g);
    }
    g.runs.push(run);
  }
  return [...groups.values()];
}

export const rangeParams = (r: Range): { from?: string; to?: string } => ({
  from: r.from?.toISOString(),
  to: r.to?.toISOString(),
});
