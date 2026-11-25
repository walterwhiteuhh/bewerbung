import { describe, expect, it } from "vitest";
import { fitZoom, mapLayout, placeCard, project, SHEET_BELOW, type MapPoint } from "./PlaceCard";

const job: MapPoint = { lat: 53.551, lon: 9.993, kind: "job", label: "Stelle" };
const home: MapPoint = { lat: 53.567, lon: 9.94, kind: "home", label: "Wohnort" };
const kiel: MapPoint = { lat: 54.323, lon: 10.135, kind: "job", label: "Kiel" };

describe("Kartenprojektion", () => {
  it("bildet Web-Mercator korrekt ab", () => {
    expect(project(0, 0, 0)).toEqual([128, 128]);
    const [x, y] = project(53.55, 9.99, 12);
    expect(Math.floor(x / 256)).toBe(2161); // bekannte OSM-Kachel für Hamburg
    expect(Math.floor(y / 256)).toBe(1323);
  });

  it("wählt nah = hohe, fern = niedrige Zoomstufe", () => {
    expect(fitZoom([job], false, 300, 150)).toBe(13);
    expect(fitZoom([job], true, 300, 150)).toBe(11);
    expect(fitZoom([job, home], false, 300, 150)).toBeGreaterThan(fitZoom([kiel, home], false, 300, 150));
  });

  it.each([
    [300, 150],
    [474, 150],
    [358, 180],
  ])("hält alle Punkte im Ausschnitt %i×%i und deckt ihn mit Kacheln ab", (w, h) => {
    const { tiles, local } = mapLayout([job, home], false, w, h);
    for (const [x, y] of local) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(w);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(h);
    }
    const left = Math.min(...tiles.map((t) => t.left));
    const top = Math.min(...tiles.map((t) => t.top));
    const right = Math.max(...tiles.map((t) => t.left + 256));
    const bottom = Math.max(...tiles.map((t) => t.top + 256));
    expect(left).toBeLessThanOrEqual(0);
    expect(top).toBeLessThanOrEqual(0);
    expect(right).toBeGreaterThanOrEqual(w);
    expect(bottom).toBeGreaterThanOrEqual(h);
  });
});

describe("Position der Info-Karte", () => {
  const trigger = { left: 100, top: 200, bottom: 220 };

  it("erscheint auf schmalen Geräten als Bottom-Sheet", () => {
    expect(placeCard(trigger, 300, SHEET_BELOW - 1, 800).sheet).toBe(true);
  });

  it("öffnet unter dem Auslöser, wenn Platz ist", () => {
    expect(placeCard(trigger, 300, 1366, 900)).toEqual({ left: 100, top: 228, above: false, sheet: false });
  });

  it("öffnet darüber, wenn unten kein Platz ist", () => {
    const r = placeCard({ left: 100, top: 700, bottom: 720 }, 300, 1366, 800);
    expect(r).toMatchObject({ above: true, top: 392, sheet: false });
  });

  it("wird zum Sheet, wenn weder oben noch unten Platz ist", () => {
    expect(placeCard({ left: 100, top: 300, bottom: 320 }, 500, 1024, 640).sheet).toBe(true);
  });

  it("bleibt horizontal im Fenster", () => {
    const r = placeCard({ left: 1300, top: 100, bottom: 120 }, 300, 1366, 900);
    expect(r.left + 316).toBeLessThanOrEqual(1366 - 12);
  });
});
