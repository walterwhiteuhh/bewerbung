import type { Stats } from "../api/types";
import { voyageFrom } from "./voyage";

export interface TickerItem {
  id: string;
  text: string;
  href: string; // Hash-Ziel in der App oder auf der Startseite
  live?: boolean; // stammt aus den eigenen Daten
}

/** Immer vorhandene Meldungen: kleine Tipps, jede führt an die passende Stelle. */
export const STATIC_ITEMS: TickerItem[] = [
  { id: "portale", text: "Vier Portale, eine Suche: Arbeitsagentur, Jooble, Arbeitnow, Remotive", href: "#/suche" },
  { id: "link", text: "Tipp: Anzeigen von LinkedIn oder StepStone per Link übernehmen", href: "#/" },
  { id: "ki", text: "Anschreiben-Entwurf per Claude, GPT oder Gemini in Sekunden", href: "#/" },
  { id: "tags", text: "Mit #Hashtags Stellen sortieren und blitzschnell wiederfinden", href: "#/" },
  { id: "karte", text: "Ortsname antippen: Minikarte mit Entfernung zu dir", href: "#/suche" },
  { id: "tag", text: "Seewetter-Tipp: Täglich ein Blick in die Liste hält die Bewerbungen auf Kurs", href: "#/" },
];

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * Meldungen aus den eigenen Kennzahlen („Seewetterbericht“). Ohne Daten (Server nicht erreichbar,
 * noch keine Stellen) bleiben nur die statischen Meldungen, nichts wird erfunden.
 */
export function liveItems(stats: Stats | undefined): TickerItem[] {
  if (!stats || stats.total === 0) return [];
  const v = voyageFrom(stats);
  const items: TickerItem[] = [
    { id: "wetter", text: `Seewetter: ${v.windLabel}, ${plural(v.activity, "Statuswechsel", "Statuswechsel")} in 7 Tagen`, href: "#/", live: true },
    { id: "an-bord", text: `${plural(stats.total, "Stelle", "Stellen")} an Bord, ${v.active} im Rennen`, href: "#/", live: true },
  ];
  if (v.interviews > 0) items.push({ id: "gespraeche", text: `${plural(v.interviews, "Vorstellungsgespräch", "Vorstellungsgespräche")} voraus`, href: "#/", live: true });
  if (v.offers > 0) items.push({ id: "angebot", text: `${plural(v.offers, "Angebot", "Angebote")}: Leuchtfeuer gesichtet!`, href: "#/", live: true });
  if (v.accepted > 0) items.push({ id: "land", text: "Land in Sicht: Zusage erhalten", href: "#/", live: true });
  return items;
}

/** Live-Meldungen vorn, dazwischen die Tipps im Wechsel. */
export function tickerItems(stats: Stats | undefined): TickerItem[] {
  const live = liveItems(stats);
  const tips = [...STATIC_ITEMS];
  const out: TickerItem[] = [];
  while (live.length || tips.length) {
    const l = live.shift();
    if (l) out.push(l);
    const t = tips.shift();
    if (t) out.push(t);
  }
  return out;
}
