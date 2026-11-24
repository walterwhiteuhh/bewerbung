const dateFmt = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });
const rtf = new Intl.RelativeTimeFormat("de-DE", { numeric: "auto" });

export const formatDate = (iso: string | null | undefined) => (iso ? dateFmt.format(new Date(iso)) : "–");
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso));

export function relativeTime(iso: string): string {
  const diffSec = (new Date(iso).getTime() - Date.now()) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, secs] of units) {
    if (Math.abs(diffSec) >= secs) return rtf.format(Math.round(diffSec / secs), unit);
  }
  return "gerade eben";
}

export function formatSalary(min: number | null, max: number | null, currency: string): string | null {
  if (min === null && max === null) return null;
  const f = new Intl.NumberFormat("de-DE", { style: "currency", currency, maximumFractionDigits: 0 });
  if (min !== null && max !== null) return `${f.format(min)} – ${f.format(max)}`;
  return min !== null ? `ab ${f.format(min)}` : `bis ${f.format(max!)}`;
}

/** ISO-Datum (YYYY-MM-DD) aus <input type="date"> als lokale Mitternacht mit Offset. */
export function localDateToIso(value: string): string | null {
  if (!value) return null;
  return new Date(`${value}T09:00:00`).toISOString();
}

export const isoToLocalDate = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
