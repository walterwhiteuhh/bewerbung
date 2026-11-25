import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useProfile } from "../api/hooks";
import type { JobFeatures } from "../api/types";
import { SOURCE_LABEL } from "../lib/labels";
import { CompanyLogo } from "./CompanyLogo";
import { distanceLabel } from "./Insights";
import { SocialLinks } from "./SocialLinks";

// --- Minikarte aus OpenStreetMap-Kacheln (ohne Kartenbibliothek) -------------------

const TILE = 256;
const MAP_W = 300;
const MAP_H = 150;

interface MapPoint {
  lat: number;
  lon: number;
  kind: "job" | "home";
  label: string;
}

/** Web-Mercator: Grad -> Weltpixel bei Zoomstufe z. */
function project(lat: number, lon: number, z: number): [number, number] {
  const scale = TILE * 2 ** z;
  const rad = (Math.max(Math.min(lat, 85), -85) * Math.PI) / 180;
  return [((lon + 180) / 360) * scale, ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * scale];
}

function fitZoom(points: MapPoint[], estimated: boolean): number {
  if (points.length < 2) return estimated ? 11 : 13;
  for (let z = 13; z > 3; z--) {
    const px = points.map((p) => project(p.lat, p.lon, z));
    const w = Math.max(...px.map((p) => p[0])) - Math.min(...px.map((p) => p[0]));
    const h = Math.max(...px.map((p) => p[1])) - Math.min(...px.map((p) => p[1]));
    if (w <= MAP_W - 56 && h <= MAP_H - 56) return z;
  }
  return 3;
}

export function MiniMap({ points, estimated = false }: { points: MapPoint[]; estimated?: boolean }) {
  const z = fitZoom(points, estimated);
  const px = points.map((p) => project(p.lat, p.lon, z));
  const cx = (Math.min(...px.map((p) => p[0])) + Math.max(...px.map((p) => p[0]))) / 2;
  const cy = (Math.min(...px.map((p) => p[1])) + Math.max(...px.map((p) => p[1]))) / 2;
  const x0 = cx - MAP_W / 2;
  const y0 = cy - MAP_H / 2;
  const n = 2 ** z;
  const tiles: { x: number; y: number; left: number; top: number }[] = [];
  for (let tx = Math.floor(x0 / TILE); tx <= Math.floor((x0 + MAP_W) / TILE); tx++) {
    for (let ty = Math.floor(y0 / TILE); ty <= Math.floor((y0 + MAP_H) / TILE); ty++) {
      if (ty < 0 || ty >= n) continue;
      tiles.push({ x: ((tx % n) + n) % n, y: ty, left: tx * TILE - x0, top: ty * TILE - y0 });
    }
  }
  const local = px.map(([x, y]) => [x - x0, y - y0] as const);
  const at = (kind: MapPoint["kind"]) => {
    const i = points.findIndex((p) => p.kind === kind);
    return i >= 0 ? local[i] : undefined;
  };
  const job = at("job");
  const home = at("home");

  return (
    <div className="minimap" role="img" aria-label={points.map((p) => p.label).join(", ")}>
      {tiles.map((t) => (
        <img
          key={`${t.x}-${t.y}-${t.left}`}
          className="minimap__tile"
          src={`https://tile.openstreetmap.org/${z}/${t.x}/${t.y}.png`}
          style={{ left: t.left, top: t.top }}
          alt=""
          loading="lazy"
          draggable={false}
          onError={(e) => (e.currentTarget.style.visibility = "hidden")}
        />
      ))}
      <svg className="minimap__overlay" viewBox={`0 0 ${MAP_W} ${MAP_H}`} aria-hidden>
        {job && home && <line x1={home[0]} y1={home[1]} x2={job[0]} y2={job[1]} className="minimap__route" />}
        {job && estimated && <circle cx={job[0]} cy={job[1]} r={22} className="minimap__area" />}
        {points.map((p, i) => {
          const [x, y] = local[i] ?? [0, 0];
          return p.kind === "home" ? (
            <g key={i} transform={`translate(${x} ${y})`} className="minimap__home">
              <circle r={9} />
              <path d="M-4.5 0.5 0-3.8 4.5 0.5M-3 -0.6V3.6h6V-0.6" />
            </g>
          ) : (
            <g key={i} transform={`translate(${x} ${y})`} className="minimap__job">
              <path d="M0 0c-1.4-4.6-8-7.4-8-13a8 8 0 0 1 16 0c0 5.6-6.6 8.4-8 13Z" />
              <circle cy={-13} r={3} />
            </g>
          );
        })}
      </svg>
      <span className="minimap__credit">© OpenStreetMap</span>
    </div>
  );
}

// --- Hover-Karte ---------------------------------------------------------------------

export interface PlaceInfo {
  location: string | null;
  companyName: string | null;
  companyLogo?: string | null;
  features: JobFeatures | null | undefined;
  loading?: boolean;
}

function osmLink(lat: number, lon: number): string {
  return `https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&mlon=${lon.toFixed(5)}#map=13/${lat.toFixed(4)}/${lon.toFixed(4)}`;
}

function routeLink(from: [number, number], to: [number, number]): string {
  const p = (c: [number, number]) => `${c[0].toFixed(5)}%2C${c[1].toFixed(5)}`;
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${p(from)}%3B${p(to)}`;
}

function PlaceCardBody({ info }: { info: PlaceInfo }) {
  const { data: profile } = useProfile();
  const f = info.features;
  const home: [number, number] | null =
    profile?.home_lat != null && profile?.home_lon != null ? [profile.home_lat, profile.home_lon] : null;
  const job: [number, number] | null = f?.lat != null && f?.lon != null ? [f.lat, f.lon] : null;
  const place = [f?.postal_code, f?.city].filter(Boolean).join(" ") || info.location || "Ort unbekannt";
  const region = f?.region && f.region !== f.city ? f.region : null;
  const points: MapPoint[] = [];
  if (job) points.push({ lat: job[0], lon: job[1], kind: "job", label: `Stelle: ${place}` });
  if (job && home) points.push({ lat: home[0], lon: home[1], kind: "home", label: `Wohnort: ${profile?.home_location ?? ""}` });
  const dist = f ? distanceLabel(f) : null;
  const c = f?.company;

  return (
    <>
      {job ? (
        <MiniMap points={points} estimated={f?.position_estimated} />
      ) : (
        <div className="minimap minimap--empty">{info.loading ? "Lade Ort …" : "Für diesen Ort sind keine Koordinaten bekannt."}</div>
      )}
      <div className="placecard__body">
        <p className="placecard__place">
          <strong>{place}</strong>
          {region && <span className="muted"> · {region}</span>}
        </p>
        {dist ? (
          <p className="placecard__dist">
            <span className={`feat ${f?.within_max_distance === false ? "feat--warn" : f?.within_max_distance ? "feat--good" : ""}`}>{dist}</span>
            <span className="muted">
              Luftlinie von {profile?.home_location ?? "deinem Wohnort"}
              {f?.within_max_distance === false && profile?.max_distance_km ? `, über deinen Radius von ${profile.max_distance_km} km` : ""}
            </span>
          </p>
        ) : (
          !home && !info.loading && <p className="muted placecard__hint">Trag unter „Mein Profil“ deinen Wohnort ein, dann siehst du hier die Entfernung.</p>
        )}
        {f?.position_estimated && job && <p className="muted placecard__hint">Genaue Adresse fehlt, die Markierung zeigt die Stadtmitte.</p>}
        {info.companyName && (
          <div className="placecard__company">
            <CompanyLogo name={info.companyName} url={info.companyLogo} size="md" />
            <div>
              <strong>{info.companyName}</strong>
              {c && (
                <span className="muted">
                  {[
                    `${c.listings} ${c.listings === 1 ? "Anzeige" : "Anzeigen"}${c.active_listings && c.active_listings < c.listings ? `, ${c.active_listings} aktiv` : ""}`,
                    c.portals.length ? c.portals.map((p) => SOURCE_LABEL[p]).join(", ") : null,
                    c.applications ? `${c.applications}× beworben` : null,
                    c.rejections ? `${c.rejections}× Absage` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              )}
            </div>
          </div>
        )}
        {c && <SocialLinks links={c.social_links} website={c.website} />}
        {job && (
          <p className="placecard__links">
            <a href={osmLink(job[0], job[1])} target="_blank" rel="noreferrer noopener">
              Karte öffnen ↗
            </a>
            {home && (
              <a href={routeLink(home, job)} target="_blank" rel="noreferrer noopener">
                Route ↗
              </a>
            )}
          </p>
        )}
      </div>
    </>
  );
}

const OPEN_DELAY = 220;
const CLOSE_DELAY = 160;
const CARD_W = 316;

/**
 * Ort mit Info-Karte: öffnet beim Überfahren oder Fokussieren, auf Touch per Tippen.
 * `interactive=false` für Auslöser innerhalb eines Buttons (nur Maus-Hover).
 */
export function PlaceHover({
  children,
  info,
  onOpenChange,
  interactive = true,
}: {
  children: ReactNode;
  info: PlaceInfo;
  onOpenChange?: (open: boolean) => void;
  interactive?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const trigger = useRef<HTMLSpanElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const timer = useRef<number>();

  const change = useCallback(
    (next: boolean) => {
      setOpen(next);
      onOpenChange?.(next);
    },
    [onOpenChange],
  );
  const schedule = (next: boolean) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => change(next), next ? OPEN_DELAY : CLOSE_DELAY);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);

  useLayoutEffect(() => {
    if (!open || !trigger.current) return;
    const r = trigger.current.getBoundingClientRect();
    const h = card.current?.offsetHeight ?? 320;
    const width = Math.min(CARD_W, window.innerWidth - 24);
    const left = Math.min(Math.max(12, r.left), window.innerWidth - width - 12);
    const above = r.bottom + h + 12 > window.innerHeight && r.top - h - 12 > 0;
    setPos({ left, top: above ? r.top - h - 8 : r.bottom + 8, above });
  }, [open, info.features, info.loading]);

  useEffect(() => {
    if (!open) return;
    const close = () => change(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!card.current?.contains(t) && !trigger.current?.contains(t)) close();
    };
    window.addEventListener("scroll", close, true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [open, change]);

  return (
    <>
      <span
        ref={trigger}
        className={`placehover ${open ? "is-open" : ""}`}
        tabIndex={interactive ? 0 : undefined}
        role={interactive ? "button" : undefined}
        aria-expanded={interactive ? open : undefined}
        aria-label={interactive ? `Ort und Karte: ${info.location ?? ""}` : undefined}
        onPointerEnter={(e) => e.pointerType === "mouse" && schedule(true)}
        onPointerLeave={(e) => e.pointerType === "mouse" && schedule(false)}
        onFocus={interactive ? () => schedule(true) : undefined}
        onBlur={interactive ? () => schedule(false) : undefined}
        onClick={
          interactive
            ? (e) => {
                e.stopPropagation();
                window.clearTimeout(timer.current);
                change(!open);
              }
            : undefined
        }
        onKeyDown={interactive ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), change(!open)) : undefined}
      >
        <svg viewBox="0 0 24 24" aria-hidden className="placehover__pin">
          <path d="M12 21s-7-6.1-7-11.5a7 7 0 0 1 14 0C19 14.9 12 21 12 21Z" />
          <circle cx="12" cy="9.5" r="2.5" />
        </svg>
        {children}
      </span>
      {open &&
        createPortal(
          <div
            ref={card}
            className={`placecard ${pos?.above ? "is-above" : ""}`}
            style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, width: Math.min(CARD_W, window.innerWidth - 24) }}
            role="dialog"
            aria-label="Ort und Firma"
            onPointerEnter={(e) => e.pointerType === "mouse" && window.clearTimeout(timer.current)}
            onPointerLeave={(e) => e.pointerType === "mouse" && schedule(false)}
            onClick={(e) => e.stopPropagation()}
          >
            <PlaceCardBody info={info} />
          </div>,
          document.body,
        )}
    </>
  );
}
