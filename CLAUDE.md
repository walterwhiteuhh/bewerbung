# CLAUDE.md

@docs/leitfaden-maritime-webapps.md

Der importierte Leitfaden ist die Basis für Stack, Struktur, maritimes Design, Responsive, Android (Capacitor) und Datenregeln. Hier steht nur, was **Anheuern** davon unterscheidet oder zusätzlich braucht. Bei Widerspruch gilt diese Datei.

## Projekt
Anheuern („Kurs auf den nächsten Job“): Stellenanzeigen aus Portalen finden, Bewerbungen steuern, Anschreiben erstellen. Python-Paket und Ordner heißen `bewerbung`. Funktionsüberblick, Datenmodell und API: `README.md`.

## Abweichungen vom Leitfaden
| Thema | Leitfaden | Anheuern |
|---|---|---|
| Paketmanager | pnpm | npm (`frontend/`), uv (Backend) |
| Frontend-Pfad | Wurzel (`src/`) | `frontend/src/` |
| Struktur | `features/`, `shared/` | `components/`, `lib/`, `api/` (flach) |
| Styling | Tailwind + `tokens.css` | Handgeschriebenes mobile-first CSS in `frontend/src/styles.css` |
| Routing | TanStack Router | keins (eine Seite, Zustand in `App.tsx`) |
| UI-State | Zustand | React-State |
| React | 19 | 18.3 |
| Backend | FastAPI + PostgreSQL | FastAPI + SQLite (`data/bewerbung.db`), Alembic |
| Android/Capacitor | Ziel | noch nicht umgesetzt; bei Einführung `shared/platform`-Abstraktion anlegen |
| Design | Tokens, Nachtmodus | Tageszeit-Szene (`ShipScene.tsx`), Schrift Bricolage Grotesque + IBM Plex Sans |

Angleichung ist kein Ziel an sich; Migration nur, wenn sie einen konkreten Nutzen hat.

## Befehle
- Backend: `uv sync`, `uv run bewerbung`, `uv run pytest`, `uv run ruff check src tests`, `uv run mypy src`
- Frontend (in `frontend/`): `npm run dev`, `npm run typecheck`, `npm test`, `npm run build && npm run test:e2e`
- Vor Abschluss alle Checks laufen lassen, die zur Änderung passen. CI (`.github/workflows/ci.yml`) führt alles aus.

## Anheuern-spezifisch
- Backend-Schichten: `domain/` (kein HTTP, keine DB) → `db/` → `services/` → `api/`; Quellen über `SourceAdapter` in `sources/`.
- Datenregeln des Leitfadens sind hier umgesetzt: `created_at`/`updated_at` überall, Soft-Delete über `archived_at`, `application_status_events` append-only und bitemporal (`occurred_at`/`recorded_at`). Nicht aufweichen. Migrationen immer über Alembic.
- `raw_payload` und Zeitstempel der Rohdaten erhalten; Merkmale für spätes Ranking nie rückwirkend überschreiben.
- Responsive-Tests (`frontend/e2e/responsive.spec.ts`, 320 px bis 4K) sind Pflicht für jede UI-Änderung; Touchziele ≥ 32 px, kein seitliches Scrollen, `minmax(0, 1fr)` in Grids.
- Importe laden nur die eine angegebene Seite; interne Adressen bleiben gesperrt (SSRF-Schutz). KI-Keys nur über `.env`.
- Antworten und Commit-Nachrichten auf Deutsch, Code und Bezeichner auf Englisch.
