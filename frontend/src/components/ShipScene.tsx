/**
 * Segelschiff auf bewegter See: reines SVG, animiert nur per CSS-Transform/Opacity (GPU).
 *
 * Kleine Überraschungen:
 * - Die Szene folgt der echten Uhrzeit: Morgenrot, Tag, Abendrot, Nacht mit Mond,
 *   funkelnden Sternen, Leuchtturm und Laterne an Bord.
 * - Ab und zu taucht ein Wal auf und bläst.
 * - Antippen ruft „Ahoi!“: Das Schiff springt über die Welle, dazu ein Seemannsspruch.
 *
 * Mit `voyage` zeigt die Szene Kennzahlen (siehe lib/voyage.ts): Seegang = Aktivität der
 * letzten 7 Tage, Wimpel = laufende Bewerbungen, Bojen = Gespräche, Leuchtfeuer = Angebot,
 * Insel = Zusage. Ein Logbuch darunter erklärt die Symbole.
 */
import { useEffect, useState } from "react";

import { logbook, type Voyage } from "../lib/voyage";

// Eine Wellenperiode = 60 Einheiten; die Fläche ist doppelt so breit wie die Szene,
// damit eine Verschiebung um 240 nahtlos wiederholt werden kann.
function wave(y: number, amp: number): string {
  let d = `M0 ${y}`;
  for (let x = 0; x < 480; x += 60) d += ` q15 ${-amp} 30 0 t30 0`;
  return `${d} V160 H0 Z`;
}

const BACK = wave(112, 7);
const MID = wave(120, 9);
const FRONT = wave(130, 8);

export type Phase = "dawn" | "day" | "dusk" | "night";

/** Tageszeit nach lokaler Stunde (0–23). Grob für Norddeutschland, ohne Jahreszeiten. */
export function phaseAt(hour: number): Phase {
  if (hour >= 5 && hour < 8) return "dawn";
  if (hour >= 8 && hour < 17) return "day";
  if (hour >= 17 && hour < 21) return "dusk";
  return "night";
}

export const SAYINGS = [
  "Ahoi!",
  "Leinen los!",
  "Klar Schiff!",
  "Volle Fahrt voraus!",
  "Mast- und Schotbruch!",
  "Land in Sicht!",
] as const;

// Sterne: feste Positionen, damit der Himmel bei jedem Rendern gleich aussieht.
const STARS: [number, number, number][] = [
  [22, 18, 1.1], [48, 34, 0.8], [74, 14, 1], [98, 40, 0.7], [140, 12, 0.9],
  [158, 30, 0.7], [214, 20, 1], [228, 52, 0.8], [36, 60, 0.7], [176, 60, 0.6],
];  // prettier-ignore

function usePhase(fixed?: Phase): Phase {
  const [phase, setPhase] = useState<Phase>(() => fixed ?? phaseAt(new Date().getHours()));
  useEffect(() => {
    if (fixed) {
      setPhase(fixed);
      return;
    }
    const id = window.setInterval(() => setPhase(phaseAt(new Date().getHours())), 5 * 60_000);
    return () => window.clearInterval(id);
  }, [fixed]);
  return phase;
}

// Wimpelleine vom Masttopp zum Heck; Wimpel hängen gleichmäßig verteilt daran.
const LINE: [number, number, number, number] = [120, 28, 52, 104];
const PENNANT_COLORS = ["var(--marker)", "var(--accent)", "var(--s-offer)", "var(--s-rejected)"];
const BUOY_X = [34, 60, 184, 206, 226];

function pennants(n: number) {
  const [x1, y1, x2, y2] = LINE;
  return Array.from({ length: n }, (_, i) => {
    const t = (i + 1) / (n + 1);
    const x = x1 + (x2 - x1) * t;
    const y = y1 + (y2 - y1) * t;
    return { x, y, color: PENNANT_COLORS[i % PENNANT_COLORS.length] };
  });
}

interface Props {
  size?: "sm" | "md";
  phase?: Phase;
  voyage?: Voyage;
}

export function ShipScene({ size = "md", phase: fixed, voyage }: Props) {
  const phase = usePhase(fixed);
  const [ahoy, setAhoy] = useState(0); // Zähler: jede Berührung startet die Animation neu
  const saying = ahoy > 0 ? SAYINGS[(ahoy - 1) % SAYINGS.length] : null;
  const log = voyage ? logbook(voyage) : [];
  const label = ["Segelschiff auf bewegter See", ...log.map((e) => e.label), "Antippen für Ahoi!"].join(". ");

  const scene = (
    <button type="button" className={`ship-btn ship-btn--${size}`} onClick={() => setAhoy((n) => n + 1)} aria-label={label}>
      <span className="sr-only" aria-live="polite">
        {saying}
      </span>
      <svg
        className="ship"
        data-phase={phase}
        data-wind={voyage?.wind}
        data-offer={voyage && voyage.offers > 0 ? "" : undefined}
        viewBox="0 0 240 160"
        aria-hidden="true"
      >
        <rect className="ship__sky" width="240" height="160" />
        <g className="ship__stars">
          {STARS.map(([x, y, r], i) => (
            <circle key={i} cx={x} cy={y} r={r} style={{ animationDelay: `${(i * 0.37) % 2.4}s` }} />
          ))}
        </g>
        <circle className="ship__sun" cx="192" cy="38" r="16" />
        <g className="ship__moon">
          <circle cx="192" cy="36" r="13" />
          <circle className="ship__moon-cut" cx="199" cy="31" r="11" />
        </g>
        <g className="ship__gull">
          <path d="M40 40q5-5 10 0q5-5 10 0" />
          <path d="M66 28q4-4 8 0q4-4 8 0" />
        </g>
        <g className="ship__coast">
          <path d="M0 104q18-10 40-6t36 8V112H0Z" />
          <path className="ship__tower" d="M22 100l2-18h4l2 18Z" />
          <path className="ship__beam" d="M26 84L118 66V102Z" />
          <circle className="ship__lamp" cx="26" cy="84" r="2.2" />
        </g>
        {voyage && voyage.accepted > 0 && (
          <g className="ship__island">
            <path d="M190 113q20-16 46 0Z" />
            <path className="ship__palm" d="M214 106q-1-10 3-17" />
            <path className="ship__frond" d="M217 89q-8-3-13 3M217 89q7-5 13 1M217 89q-3-6-9-7M217 89q4-6 10-5" />
          </g>
        )}
        <g className="ship__swell">
          <path className="ship__wave ship__wave--back" d={BACK} />
        </g>
        <g className="ship__whale">
          <path d="M178 126Q186 108 202 107Q216 107 226 122L230 126Z" />
          <path d="M207 108l5-8 1 9Z" />
          <path className="ship__spout" d="M196 106q-3-8-8-10M196 106q0-9 1-13M196 106q3-8 8-10" />
        </g>
        <g className="ship__boat">
          <g className={ahoy ? "ship__hop is-hopping" : "ship__hop"} key={ahoy}>
            <g className="ship__rock">
              <path className="ship__mast" d="M120 26V110" />
              <path className="ship__sail" d="M125 32Q160 64 164 102H125Z" />
              <path className="ship__sail ship__sail--front" d="M115 40Q90 70 82 102H115Z" />
              <path className="ship__flag" d="M120 26l14 5-14 5z" />
              {voyage && voyage.pennants > 0 && (
                <g className="ship__pennants">
                  <path className="ship__line" d={`M${LINE[0]} ${LINE[1]}L${LINE[2]} ${LINE[3]}`} />
                  {pennants(voyage.pennants).map((p, i) => (
                    <path key={i} d={`M${p.x - 4.5} ${p.y}h9l-4.5 10z`} fill={p.color} />
                  ))}
                </g>
              )}
              {voyage && voyage.pennants > 0 && <path className="ship__sprit" d="M76 109L52 104" />}
              <path className="ship__hull" d="M72 108H170L157 128H86Z" />
              <path className="ship__stripe" d="M80 115H164" />
              <circle className="ship__lantern" cx="164" cy="104" r="2.6" />
            </g>
          </g>
        </g>
        <g className="ship__swell">
          <path className="ship__wave ship__wave--mid" d={MID} />
        </g>
        {voyage &&
          BUOY_X.slice(0, voyage.buoys).map((x, i) => (
            <g key={x} className="ship__buoy" style={{ animationDelay: `${-i * 0.7}s` }}>
              <path d={`M${x - 6} 130h12l-2.4-15h-7.2Z`} />
              <path className="ship__buoy-band" d={`M${x - 5} 124h10`} />
              <circle className="ship__buoy-light" cx={x} cy={112} r={2.2} />
            </g>
          ))}
        <g className="ship__swell">
          <path className="ship__wave ship__wave--front" d={FRONT} />
        </g>
        {saying && (
          <g className="ship__bubble" key={`b${ahoy}`}>
            <rect x="8" y="8" width="112" height="22" rx="11" />
            <text x="64" y="23" textAnchor="middle">
              {saying}
            </text>
          </g>
        )}
      </svg>
    </button>
  );

  if (!voyage) return scene;
  return (
    <figure className={`voyage voyage--${size}`}>
      {scene}
      <figcaption className="voyage__log" aria-hidden="true">
        {log.map((e) => (
          <span key={e.key} className={`voyage__entry voyage__entry--${e.key}`}>
            {e.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
