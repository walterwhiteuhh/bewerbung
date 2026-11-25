import type { Stats } from "../api/types";

/**
 * Übersetzt Kennzahlen in die Seefahrt-Szene. Reine Funktion, damit die Zuordnung
 * testbar bleibt und die Szene selbst nur noch zeichnet.
 */
export interface Voyage {
  wind: 0 | 1 | 2 | 3; // Flaute .. steife Brise, aus den Statuswechseln der letzten 7 Tage
  windLabel: string;
  activity: number;
  pennants: number; // laufende Bewerbungen (max. 8 gezeichnet)
  active: number;
  buoys: number; // Vorstellungsgespräche (max. 5 gezeichnet)
  interviews: number;
  offers: number; // Leuchtturm leuchtet
  accepted: number; // Land in Sicht
}

export const MAX_PENNANTS = 8;
export const MAX_BUOYS = 5;
const WIND_LABELS = ["Flaute", "leichte Brise", "frische Brise", "steife Brise"] as const;

export function windLevel(activity7d: number): Voyage["wind"] {
  if (activity7d <= 0) return 0;
  if (activity7d <= 3) return 1;
  if (activity7d <= 9) return 2;
  return 3;
}

export function voyageFrom(stats: Stats): Voyage {
  const count = (key: string) => stats.by_status.find((b) => b.key === key)?.count ?? 0;
  const wind = windLevel(stats.activity_7d);
  const interviews = count("interview");
  return {
    wind,
    windLabel: WIND_LABELS[wind],
    activity: stats.activity_7d,
    active: stats.active,
    pennants: Math.min(stats.active, MAX_PENNANTS),
    interviews,
    buoys: Math.min(interviews, MAX_BUOYS),
    offers: count("offer"),
    accepted: count("accepted"),
  };
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Logbuch-Einträge unter der Szene: Symbol erklären, Zahl nennen. */
export function logbook(v: Voyage): { key: string; label: string }[] {
  const steps = plural(v.activity, "Schritt", "Schritte");
  const wind = v.windLabel.charAt(0).toUpperCase() + v.windLabel.slice(1);
  const entries = [{ key: "wind", label: `${wind}: ${steps} in 7 Tagen` }];
  if (v.active) entries.push({ key: "pennant", label: `${`${v.active} Wimpel`} = laufende Bewerbungen` });
  if (v.interviews) entries.push({ key: "buoy", label: `${plural(v.interviews, "Boje", "Bojen")} = ${v.interviews === 1 ? "Gespräch" : "Gespräche"}` });
  if (v.offers) entries.push({ key: "light", label: `Leuchtfeuer: ${plural(v.offers, "Angebot", "Angebote")}` });
  if (v.accepted) entries.push({ key: "land", label: "Land in Sicht: Zusage!" });
  return entries;
}
