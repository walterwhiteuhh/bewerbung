/**
 * Newsticker „Neues aus dem Hafen“: endlos laufende Meldungen (Tipps plus echte Kennzahlen,
 * wenn die App Daten hat). Interaktiv: pausiert bei Hover und Fokus, per Knopf anhaltbar,
 * jede Meldung ist ein Link. Bei reduzierter Bewegung steht er still und bricht um.
 */
import { useState } from "react";

import { useStats } from "../api/hooks";
import { tickerItems, type TickerItem } from "../lib/ticker";

function Track({ items, hidden }: { items: TickerItem[]; hidden?: boolean }) {
  return (
    <ul className="lp-ticker__track" aria-hidden={hidden || undefined}>
      {items.map((it) => (
        <li key={it.id}>
          <a
            href={it.href}
            tabIndex={hidden ? -1 : undefined}
            className={it.live ? "is-live" : ""}
          >
            {it.live && <i aria-hidden />}
            {it.text}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function Ticker() {
  const { data: stats } = useStats();
  const items = tickerItems(stats);
  const [paused, setPaused] = useState(false);

  return (
    <section
      className="lp-ticker"
      aria-label="Neues aus dem Hafen"
      data-paused={paused || undefined}
    >
      <span className="lp-ticker__label" aria-hidden>
        <span className="lp-ticker__long">Neues aus dem </span>Hafen
      </span>
      <div className="lp-ticker__window">
        <div className="lp-ticker__belt">
          <Track items={items} />
          <Track items={items} hidden />
        </div>
      </div>
      <button
        type="button"
        className="lp-ticker__toggle"
        aria-pressed={paused}
        onClick={() => setPaused((p) => !p)}
      >
        <span className="sr-only">
          {paused ? "Ticker fortsetzen" : "Ticker anhalten"}
        </span>
        <svg viewBox="0 0 24 24" aria-hidden>
          {paused ? (
            <path d="M8 5v14l11-7z" />
          ) : (
            <path d="M7 5h3v14H7zM14 5h3v14h-3z" />
          )}
        </svg>
      </button>
    </section>
  );
}
