/** Segelschiff auf bewegter See: reines SVG, animiert nur per CSS-Transform (GPU, ~2 KB). */

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

export function ShipScene({ size = "md" }: { size?: "sm" | "md" }) {
  return (
    <svg className={`ship ship--${size}`} viewBox="0 0 240 160" role="img" aria-label="Segelschiff auf bewegter See">
      <rect className="ship__sky" width="240" height="160" />
      <circle className="ship__sun" cx="192" cy="38" r="16" />
      <g className="ship__gull">
        <path d="M40 40q5-5 10 0q5-5 10 0" />
        <path d="M66 28q4-4 8 0q4-4 8 0" />
      </g>
      <path className="ship__wave ship__wave--back" d={BACK} />
      <g className="ship__boat">
        <g className="ship__rock">
          <path className="ship__mast" d="M120 26V110" />
          <path className="ship__sail" d="M125 32Q160 64 164 102H125Z" />
          <path className="ship__sail ship__sail--front" d="M115 40Q90 70 82 102H115Z" />
          <path className="ship__flag" d="M120 26l14 5-14 5z" />
          <path className="ship__hull" d="M72 108H170L157 128H86Z" />
          <path className="ship__stripe" d="M80 115H164" />
        </g>
      </g>
      <path className="ship__wave ship__wave--mid" d={MID} />
      <path className="ship__wave ship__wave--front" d={FRONT} />
    </svg>
  );
}
