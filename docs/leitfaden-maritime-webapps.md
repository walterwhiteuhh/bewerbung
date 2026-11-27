<!--
Kopie des Basis-Leitfadens "Responsive Webapps mit maritimem Look & Feel (React + Android)".
Quelle: https://claude.ai/artifact/8dXgDgzcaw67W2HqyCDRrv (Stand: 2026-11-26)
Nicht hier ändern: Änderungen an der Quelle vornehmen und die Kopie ersetzen.
Projektspezifische Abweichungen stehen in ../CLAUDE.md und ../AGENTS.md.
-->

# Leitfaden: Responsive Webapps mit maritimem Look & Feel (React + Android)

Kompakter, wiederverwendbarer Leitfaden. Er legt Leitplanken fest, keine Implementierung.

## 1. Entscheidungen auf einen Blick

| Thema | Entscheidung | Kurzbegründung |
|---|---|---|
| Frontend | React 19 + TypeScript (strict) + Vite | Schnell, schlank, kein Framework-Lock-in |
| Routing / Daten | TanStack Router + TanStack Query | Server-State sauber getrennt von UI-State |
| UI-State | Zustand (nur wo nötig) | Kein Redux-Overhead |
| Styling | Tailwind CSS + Design Tokens (CSS-Variablen) | Mobile-First, Theme zentral steuerbar |
| Komponenten | Radix UI / shadcn/ui als Basis | Barrierefrei, eigenes maritimes Theme |
| Validierung | Zod (Schemas = Single Source of Truth für Typen) | Laufzeit- und Typsicherheit |
| Backend (falls nötig) | Python 3.11+ / FastAPI + Pydantic, PostgreSQL | Passt zur Data-Science-Pipeline, typsicher |
| Tests | Vitest + Testing Library, Playwright (E2E) | Standard, schnell |
| Android | **Capacitor** um dieselbe React-App | Siehe Abschnitt 4 |

## 2. Architektur und Projektstruktur

Prinzip: **Präsentation, Logik und Datenzugriff getrennt.** Komponenten rendern nur; Fachlogik liegt in reinen Funktionen/Hooks; Netzwerk nur in einer API-Schicht.

```text
.
├── CLAUDE.md                 # Anweisungen für Claude Code
├── AGENTS.md                 # Anweisungen für beliebige Coding-Agents
├── docs/
│   ├── ARCHITECTURE.md       # Kurzüberblick + Entscheidungen (ADR-Stil)
│   └── DESIGN.md             # Design-Tokens, Komponentenregeln
├── src/
│   ├── app/                  # Router, Provider, Layout-Shell
│   ├── features/<name>/      # je Feature: components/, hooks/, model/, api/
│   ├── shared/
│   │   ├── ui/               # Design-System-Bausteine (Button, Card, ...)
│   │   ├── lib/              # reine Hilfsfunktionen
│   │   ├── api/              # HTTP-Client, Fehlerbehandlung
│   │   └── platform/         # Web/Android-Abstraktion (Kamera, GPS, Push)
│   ├── styles/               # tokens.css, global.css
│   └── main.tsx
├── android/                  # von Capacitor generiert
├── capacitor.config.ts
├── tests/e2e/
└── package.json
```

Regeln: Features importieren nur aus `shared/` und sich selbst, nie quer untereinander. Plattformspezifisches (Android) ausschließlich hinter `shared/platform/`.

## 3. Maritimer Look & Feel

Umsetzung über **Design Tokens**, nicht über verstreute Farbwerte. Ein Theme-Wechsel (hell/dunkel/Nachtmodus) geschieht dann an einer Stelle.

```css
/* src/styles/tokens.css */
:root {
  --color-navy-900: #0b1f3a;   /* Tiefsee, Header, Primärtext auf hell */
  --color-navy-700: #14325c;
  --color-ocean-500: #1b6ca8;  /* Primäraktion */
  --color-sea-300: #7fb7d6;    /* Akzent, Hover */
  --color-foam-50:  #f4f8fb;   /* Hintergrund */
  --color-sand-200: #e8dcc2;   /* warmer Kontrast */
  --color-signal-500: #e4572e; /* Warnung / Signalrot */
  --color-buoy-400:  #f2b134;  /* Hinweis / Bojen-Gelb */

  --radius: 0.5rem;
  --font-sans: "Inter", system-ui, sans-serif;
  --touch-min: 44px;           /* Mindest-Touchziel */
}
:root[data-theme="night"] {    /* Nachtmodus: rotarm, blendarm für Brücke/Deck */
  --color-foam-50: #0b1424;
  --color-navy-900: #d6e4f0;
}
```

Leitplanken:

- Ruhige, kontrastreiche Flächen; Wellen, Kompassrose, Seil-/Knoten-Motive nur als dezente Akzente (SVG), nie als Hintergrundlärm.
- **Nachtmodus von Anfang an** einplanen (Einsatz auf See, Dämmerung).
- Große Touchziele (≥ 44 px), Bedienung mit Handschuhen/nassen Händen mitdenken.
- WCAG AA Kontrast, Statusfarben nie als einziges Signal (zusätzlich Icon/Text).
- Mobile-First, Breakpoints: `sm 640 / md 768 / lg 1024 / xl 1280`.
- Offline-Toleranz: Auf See ist Konnektivität unzuverlässig (siehe Abschnitt 4 und 5).

## 4. Android-App: Optionen und Trade-off

| Option | Vorteile | Nachteile | Wann |
|---|---|---|---|
| **PWA** | Kein Store, ein Codestand, Updates sofort | Eingeschränkter Hardwarezugriff, Push/Hintergrund-GPS begrenzt | Reines Info-/Formular-Tool |
| **Capacitor** (Empfehlung) | Gleicher React-Code, Store-fähig, native Plugins (GPS, Kamera, Push, Dateien) | Webview-Performance, Plugin-Pflege | Standardfall, schnell und wartbar |
| **React Native** | Native Performance/UX | Zweite UI-Schicht, kaum Wiederverwendung der Web-Komponenten | Nur bei hohen UX-/Performance-Anforderungen |

**Empfehlung:** Capacitor. Eine Codebasis, die responsive Web-UI läuft unverändert in der App. Hardware-Zugriff wird über `shared/platform/` gekapselt, damit die Web-Version ohne Plugin-Aufrufe weiterläuft. Einstieg: erst PWA-fähig bauen (Manifest, Service Worker), dann Capacitor hinzufügen. Wechsel auf React Native lohnt nur, wenn Webview-Grenzen nachweislich stören.

Offline: Service Worker (Workbox) für Assets, TanStack Query Persistenz oder IndexedDB für Daten, Schreibaktionen in einer Outbox-Queue mit Sync, sobald Netz da ist.

## 5. Daten und Analytics-Readiness

Auch wenn zuerst nur eine Heuristik reicht: Das Schema soll spätere Auswertung und ML ermöglichen.

- Jede Tabelle: `id` (UUID/ULID), `created_at`, `updated_at` (UTC, `timestamptz`), bei Bedarf `deleted_at` (Soft Delete).
- **Keine destruktiven Updates** für fachlich relevante Zustände: Änderungen als Events/History-Tabelle (append-only), damit historische Zustände rekonstruierbar bleiben (kein Data Leakage bei späterem Training).
- Positions-/Sensordaten als Zeitreihe: `recorded_at` (Messzeit) getrennt von `created_at` (Eingangszeit), Quelle und Genauigkeit mitspeichern (`source`, `accuracy_m`).
- Saubere Typen, Einheiten explizit (SI, z. B. `speed_mps`, `heading_deg`), Enums statt Freitext.
- Indizes auf Zeit + Fremdschlüssel; Partitionierung nach Zeit, sobald Zeitreihen wachsen; Aggregationen in der Datenbank, nicht im Frontend.
- Rohdaten, Feature-Berechnung und Inferenz getrennt halten (eigene Module), damit Features in Training und Produktion identisch berechnet werden.
- Nutzungs-Events (anonymisiert, DSGVO-konform) von Anfang an optional mitloggen, um später Signale zu haben.

## 6. Vorlage: CLAUDE.md

Für neue Projekte in die Projektwurzel kopieren und Platzhalter in `<...>` ersetzen. Kurz halten: nur, was Claude nicht aus dem Code ableiten kann.

```markdown
# CLAUDE.md

## Projekt
<Name>: responsive Webapp (React + TypeScript) mit maritimem Design, zusätzlich als Android-App via Capacitor.
Zielgruppe: <z. B. Skipper, Hafenbetreiber>. Sprache der UI: Deutsch (i18n-fähig).

## Befehle
- Entwickeln: `pnpm dev`
- Typen prüfen: `pnpm typecheck`
- Lint/Format: `pnpm lint` / `pnpm format`
- Tests: `pnpm test` (Unit), `pnpm e2e` (Playwright)
- Build Web: `pnpm build`
- Android: `pnpm build && npx cap sync android && npx cap open android`

## Architektur (Kurzfassung, Details in docs/ARCHITECTURE.md)
- `src/features/<name>/` je Feature: components, hooks, model, api.
- `src/shared/ui` Design-System, `src/shared/platform` Web/Android-Abstraktion.
- Trennung: Komponenten rendern nur; Logik in Hooks/reinen Funktionen; Netzwerk nur in `api/`.
- Server-State: TanStack Query. UI-State: lokal, Zustand nur wenn nötig.

## Konventionen
- TypeScript strict, kein `any`; Schemas mit Zod, Typen daraus ableiten.
- Funktionale Komponenten, Named Exports, Dateinamen `kebab-case`.
- Styling nur über Tailwind + Tokens aus `src/styles/tokens.css`. Keine hartcodierten Farben.
- Mobile-First; Touchziele ≥ 44 px; Nachtmodus muss funktionieren.
- Kein direkter Zugriff auf Kamera/GPS/Push außerhalb von `shared/platform`.
- Barrierefreiheit: semantisches HTML, Labels, Tastaturbedienung, Kontrast AA.
- Logging über `shared/lib/logger`, kein `console.log` im Commit.

## Daten
- Jede Entität: `id`, `created_at`, `updated_at` (UTC, ISO 8601).
- Keine destruktiven Updates bei fachlichen Zuständen; Historie erhalten.
- Einheiten explizit im Feldnamen (`speed_mps`, `heading_deg`).
- Weise aktiv darauf hin, wenn Rohdaten/Metadaten verloren gehen, die später für Analyse/ML wertvoll wären.

## Arbeitsweise
- Erst kurz planen, dann kleine, überprüfbare Änderungen.
- Vor Abschluss: `pnpm typecheck && pnpm lint && pnpm test` ausführen.
- Keine neuen Abhängigkeiten ohne kurze Begründung.
- Einfachste Lösung zuerst; keine Überabstraktion.
- Antworten und Commit-Nachrichten auf Deutsch, Code und Bezeichner auf Englisch.

## Nicht tun
- Keine Secrets committen, `.env` nicht anfassen.
- Generierte Ordner (`android/`, `dist/`) nicht von Hand ändern, außer ausdrücklich verlangt.
```

## 7. Vorlage: AGENTS.md

`AGENTS.md` ist der herstellerneutrale Standard, den viele Coding-Agents lesen. Praktisch: Inhalt dort pflegen und in `CLAUDE.md` nur darauf verweisen (`@AGENTS.md`), um Doppelpflege zu vermeiden. Alternativ die Vorlage in Abschnitt 6 als Hauptdatei nutzen und `AGENTS.md` knapp halten:

```markdown
# AGENTS.md

Allgemeine Regeln für alle Coding-Agents in diesem Repository.
Projektkontext, Befehle und Konventionen: siehe `CLAUDE.md` und `docs/ARCHITECTURE.md`.

## Setup
- Node ≥ 22, pnpm ≥ 9. Installation: `pnpm install`.

## Qualitätsschranken (müssen grün sein)
1. `pnpm typecheck`
2. `pnpm lint`
3. `pnpm test`

## Code-Stil
- TypeScript strict, Zod-Schemas, Tailwind + Design Tokens.
- Eine Verantwortung pro Datei; Feature-Ordner statt Typ-Ordner.

## Pull Requests
- Kleine, thematisch geschlossene Änderungen mit kurzer Beschreibung (Was/Warum).
- Tests für neue Logik; UI-Änderungen mit Screenshot (mobil + Desktop).

## Grenzen
- Keine Änderungen an CI, Lizenz oder Secrets ohne Rückfrage.
- Keine neuen Laufzeit-Abhängigkeiten ohne Begründung.
```

## 8. Weitere nützliche Dateien

| Datei | Zweck | Inhalt (Kurz) |
|---|---|---|
| `docs/ARCHITECTURE.md` | Orientierung für Mensch und Agent | Ordnerstruktur, Datenfluss, 3 bis 5 Architekturentscheidungen mit Begründung |
| `docs/DESIGN.md` | Einheitliches Aussehen | Token-Tabelle, Komponentenregeln, Do/Don't, Nachtmodus |
| `.claude/settings.json` | Erlaubte Befehle | Allowlist für `pnpm`-Skripte, Block für `rm -rf`, `.env` |
| `.claude/commands/new-feature.md` | Wiederkehrender Ablauf | Feature-Ordner anlegen, Schema, Hook, Test, Route |
| `.editorconfig`, `eslint.config.js`, `.prettierrc` | Einheitlicher Stil | Standardkonfiguration |
| `.github/workflows/ci.yml` | Qualitätsschranken | Typecheck, Lint, Test, Build |
| `.env.example` | Konfiguration dokumentieren | Nur Schlüssel, keine Werte |

Beispiel `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Bash(pnpm *)", "Bash(npx cap sync *)"],
    "deny": ["Read(./.env)", "Bash(rm -rf *)"]
  }
}
```

## 9. Startcheckliste für ein neues Projekt

1. Vite-React-TS-Projekt anlegen, Tailwind und `tokens.css` einrichten.
2. Vorlagen aus Abschnitt 6 bis 8 kopieren, Platzhalter ersetzen.
3. Ordnerstruktur aus Abschnitt 2 anlegen, `shared/platform` mit Web-Fallbacks.
4. PWA-Grundlagen (Manifest, Service Worker), Nachtmodus testen.
5. Capacitor hinzufügen: `npx cap init`, `npx cap add android`.
6. Datenmodell mit `id`, `created_at`, `updated_at` und Historie festlegen.
7. CI mit Typecheck, Lint, Test, Build aktivieren.

## 10. Bewusst offen gelassen

Authentifizierung, konkrete Karten-/Navigationsbibliothek (z. B. MapLibre mit Seekarten), Push-Anbieter und Hosting hängen vom Projekt ab und werden pro Vorhaben entschieden.
