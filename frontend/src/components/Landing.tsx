/**
 * Startseite im nordischen Stil: viel Luft, klare Linien, Nebel- und Fjordtöne.
 * Reines Markup + CSS (Klassen `lp-*`), keine Daten-Abfragen: die Seite lädt sofort.
 */
import { ShipScene } from "./ShipScene";
import { Ticker } from "./Ticker";

const APP_HREF = "#/";

function Anchor({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="9" />
      <g
        fill="none"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="16" cy="8.2" r="2.6" />
        <path d="M16 10.8v14.4M11 14.5h10M7.5 18.5c.6 4.4 4.2 6.9 8.5 6.9s7.9-2.5 8.5-6.9M5.8 20.4l1.7-1.9 2 1.6M26.2 20.4l-1.7-1.9-2 1.6" />
      </g>
    </svg>
  );
}

const FEATURES = [
  {
    title: "Alle Portale, ein Hafen",
    text: "Eine Suche für Arbeitsagentur, Jooble, Arbeitnow und Remotive. Anzeigen von LinkedIn, StepStone oder XING übernimmst du per Link. Doppelte Treffer werden zusammengeführt.",
  },
  {
    title: "Bewerbungen im Blick",
    text: "Vom Merken bis zur Zusage: Jeder Statuswechsel wird mit Datum festgehalten. Mit #Hashtags und Filtern findest du auch nach Wochen alles wieder.",
  },
  {
    title: "Anschreiben mit KI",
    text: "Claude, GPT, Gemini oder eine feste Vorlage schreiben aus Anzeige, Profil und Lebenslauf einen ersten Entwurf. Jede Fassung bleibt als Version erhalten.",
  },
  {
    title: "Firmen auf einen Blick",
    text: "Logo, Branche, Standort und Entfernung zu dir. Ein Tipp auf den Ort zeigt die Minikarte, Profile in sozialen Netzwerken sind direkt verlinkt.",
  },
  {
    title: "Bewertungen im Mittel",
    text: "Arbeitgeberbewertungen aus mehreren Portalen werden zu einem Wert zusammengefasst, sobald genug Stimmen vorliegen. Du trägst sie einmal ein, die App rechnet.",
  },
  {
    title: "Immer dabei",
    text: "Die App passt sich jedem Bildschirm an, vom kleinen Handy bis zum 4K-Monitor, und lässt sich auf den Startbildschirm legen. Hell oder dunkel, wie dein Gerät es mag.",
  },
] as const;

const STEPS = [
  {
    n: "01",
    title: "Finden",
    text: "Suchprofil anlegen, Portale auf einmal durchsuchen, Treffer merken.",
  },
  {
    n: "02",
    title: "Ordnen",
    text: "Stellen, Firmen und Unterlagen an einem Ort, mit Status und Notizen.",
  },
  {
    n: "03",
    title: "Anheuern",
    text: "Anschreiben entwerfen, Bewerbung abschicken, Antworten nachverfolgen.",
  },
] as const;

export function Landing() {
  return (
    <div className="lp">
      <header className="lp-nav">
        <a
          className="lp-nav__brand"
          href="#/start"
          aria-label="Anheuern, Startseite"
        >
          <Anchor className="lp-mark lp-mark--sm" />
          <span>
            An<b>heuern</b>
          </span>
        </a>
        <nav aria-label="Abschnitte" className="lp-nav__links">
          <a href="#/start/funktionen" onClick={scrollTo("funktionen")}>
            Funktionen
          </a>
          <a href="#/start/kurs" onClick={scrollTo("kurs")}>
            Kurs
          </a>
        </nav>
        <a className="lp-btn lp-btn--small" href={APP_HREF}>
          Zur App
        </a>
      </header>

      <main>
        <section className="lp-hero" aria-labelledby="lp-title">
          <div className="lp-hero__text">
            <p className="lp-eyebrow">Bewerbungen, nordisch klar</p>
            <h1 id="lp-title">
              Kurs auf den <span>nächsten Job.</span>
            </h1>
            <p className="lp-lead">
              Anheuern sammelt Stellenanzeigen aus vielen Portalen, hält jede
              Bewerbung im Blick und hilft dir beim Anschreiben. Ruhig,
              übersichtlich und ohne Zettelwirtschaft.
            </p>
            <div className="lp-cta">
              <a className="lp-btn" href={APP_HREF}>
                Zur App
                <svg viewBox="0 0 24 24" aria-hidden>
                  <path d="M5 12h14m-6-6 6 6-6 6" />
                </svg>
              </a>
              <a
                className="lp-btn lp-btn--ghost"
                href="#/start/funktionen"
                onClick={scrollTo("funktionen")}
              >
                Was kann sie?
              </a>
            </div>
          </div>
          <div className="lp-hero__art">
            <Anchor className="lp-mark lp-mark--hero" />
            <div className="lp-hero__ship">
              <ShipScene />
            </div>
          </div>
        </section>

        <Ticker />

        <div className="lp-horizon" aria-hidden>
          <span>53°33′ N</span>
          <i />
          <span>10°00′ O</span>
        </div>

        <section
          className="lp-section"
          id="funktionen"
          aria-labelledby="lp-features"
        >
          <p className="lp-eyebrow">Funktionen</p>
          <h2 id="lp-features">Alles an Bord, was eine Bewerbung braucht</h2>
          <ul className="lp-grid">
            {FEATURES.map((f) => (
              <li key={f.title} className="lp-card">
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="lp-tint" id="kurs" aria-labelledby="lp-steps">
          <div className="lp-section">
            <p className="lp-eyebrow">Der Kurs</p>
            <h2 id="lp-steps">In drei Schlägen zum Ziel</h2>
            <ol className="lp-steps">
              {STEPS.map((s) => (
                <li key={s.n}>
                  <span className="lp-steps__n">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="lp-final" aria-labelledby="lp-final">
          <Anchor className="lp-mark lp-mark--final" />
          <h2 id="lp-final">Leinen los?</h2>
          <p>Deine Daten bleiben auf deinem Rechner. Die App ist startklar.</p>
          <a className="lp-btn" href={APP_HREF}>
            Zur App
            <svg viewBox="0 0 24 24" aria-hidden>
              <path d="M5 12h14m-6-6 6 6-6 6" />
            </svg>
          </a>
        </section>
      </main>

      <footer className="lp-footer">
        <span>Anheuern · Kurs auf den nächsten Job</span>
        <span>Gebaut mit Fernweh im Norden</span>
      </footer>
    </div>
  );
}

/** Weiches Scrollen zum Abschnitt, ohne die Hash-Route (#/start) zu verlassen. */
function scrollTo(id: string) {
  return (e: React.MouseEvent) => {
    const el = document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    el.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
    el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
  };
}
