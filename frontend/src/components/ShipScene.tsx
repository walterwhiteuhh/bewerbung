/**
 * Segelschiff auf bewegter See: reines SVG, animiert nur per CSS-Transform/Opacity (GPU).
 *
 * Kleine Überraschungen:
 * - Die Szene folgt der echten Uhrzeit: Morgenrot, Tag, Abendrot, Nacht mit Mond,
 *   funkelnden Sternen, Leuchtturm und Laterne an Bord.
 * - Ab und zu taucht ein Wal auf und bläst.
 * - Antippen ruft „Ahoi!“: Das Schiff springt über die Welle, dazu ein Seemannsspruch.
 */
import { useEffect, useState } from "react";

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

export function ShipScene({ size = "md", phase: fixed }: { size?: "sm" | "md"; phase?: Phase }) {
  const phase = usePhase(fixed);
  const [ahoy, setAhoy] = useState(0); // Zähler: jede Berührung startet die Animation neu
  const saying = ahoy > 0 ? SAYINGS[(ahoy - 1) % SAYINGS.length] : null;

  return (
    <button
      type="button"
      className={`ship-btn ship-btn--${size}`}
      onClick={() => setAhoy((n) => n + 1)}
      aria-label="Segelschiff auf bewegter See. Antippen für Ahoi!"
    >
      <span className="sr-only" aria-live="polite">
        {saying}
      </span>
      <svg
        className="ship"
        data-phase={phase}
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
        <path className="ship__wave ship__wave--back" d={BACK} />
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
            <path className="ship__hull" d="M72 108H170L157 128H86Z" />
            <path className="ship__stripe" d="M80 115H164" />
            <circle className="ship__lantern" cx="164" cy="104" r="2.6" />
          </g>
          </g>
        </g>
        <path className="ship__wave ship__wave--mid" d={MID} />
        <path className="ship__wave ship__wave--front" d={FRONT} />
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
}
