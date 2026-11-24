# Bewerbungsmanager

Stellenanzeigen und Bewerbungen aus mehreren Quellen (LinkedIn, Stepstone, Karriereseiten) an einem Ort organisieren.
Iteration 1: manuelle Erfassung mit automatischer Quellen-Erkennung, Status-Historie, Notizen, Suche und Kennzahlen.
Live-Importer docken später an die Quellen-Abstraktion an.

## Schnellstart

Voraussetzungen: [uv](https://docs.astral.sh/uv/) und Node.js 20+.

```bash
# Backend-Abhängigkeiten
uv sync

# Frontend einmalig bauen (wird dann von FastAPI ausgeliefert)
cd frontend
npm install
npm run build
cd ..

# Starten: http://127.0.0.1:8000  (API-Doku: /docs)
uv run bewerbung
```

Die Datenbank liegt unter `data/bewerbung.db`, Migrationen laufen beim Start automatisch.

### Entwicklung mit Hot-Reload

```bash
uv run uvicorn bewerbung.main:create_app --factory --reload   # Terminal 1, Port 8000
cd frontend && npm run dev                                     # Terminal 2, Port 5173 (leitet /api weiter)
```

### Qualitätschecks

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src
cd frontend && npm run typecheck
```

## Architektur

```
src/bewerbung/
  domain/      Enums, Pydantic-Schemas, fachliche Fehler (kein HTTP, keine DB)
  db/          SQLAlchemy-Modelle, Engine/Session, Alembic-Migrationen
  sources/     SourceAdapter-Abstraktion + LinkedIn/Stepstone/Generic-Adapter
  services/    Geschäftslogik (Stellen, Bewerbungen, Kennzahlen)
  api/         FastAPI-Router, Dependencies, Fehler-Mapping
  main.py      App-Factory, liefert zusätzlich frontend/dist aus
frontend/      React + TypeScript + Vite, TanStack Query, mobile-first CSS
```

### Datenmodell

| Tabelle | Zweck |
|---|---|
| `companies` | Firmen, über einen normalisierten Namen (`name_key`) zusammengeführt |
| `job_postings` | Stellenanzeige mit `source`, `external_id`, `url_normalized`, `raw_payload` (Rohdaten künftiger Importer) |
| `applications` | Bewerbung zu einer Stelle; `current_status` ist eine denormalisierte Projektion für schnelle Filter |
| `application_status_events` | **Append-only** Status-Historie, bitemporal: `occurred_at` (fachlich, rückdatierbar) und `recorded_at` (Erfassung) |
| `notes` | Notizen pro Bewerbung |

Alle Tabellen haben `created_at`/`updated_at` in UTC. Löschen ist ein Soft-Delete (`archived_at`).
Dubletten werden über `(source, external_id)` (partieller Unique-Index) und die normalisierte URL erkannt.

**Warum so:** Die Event-Tabelle erlaubt später Funnel-Analysen, Durchlaufzeiten pro Stufe und
Trainingsdaten "as of" einem Stichtag ohne Data Leakage (`recorded_at <= Stichtag`).
`raw_payload` bewahrt Rohdaten der Quellen für späteres Feature Engineering (z. B. Skill-Extraktion aus Beschreibungen).

### Import aus der Anzeige

„Daten laden“ im Formular (oder Einfügen einer URL) lädt genau diese eine Seite und liest
schema.org-`JobPosting`-Daten (JSON-LD) aus, mit OpenGraph als Fallback. Die Felder werden nur
vorbefüllt, gespeichert wird erst beim Anlegen; die Rohdaten landen mit Zeitstempel und
Extraktor-Version in `raw_payload`. Interne/lokale Adressen werden nicht geladen (SSRF-Schutz).
Seiten, die automatischen Abruf blockieren (häufig LinkedIn ohne Login), liefern eine klare
Fehlermeldung; dann die Felder manuell ausfüllen.

### Neue Quelle anbinden

```python
class XingAdapter(SourceAdapter):
    source = JobSource.XING          # Enum-Wert + Alembic-Migration ergänzen
    def matches(self, parts): ...    # gehört die URL zu mir?
    def identify(self, parts): ...   # externe ID + normalisierte URL, ohne Netzwerk
    def fetch_url(self, ref, url): ...  # optional: stabilere Seite für den Import wählen

default_registry().register(XingAdapter())
```

## API (Auszug)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/sources/detect?url=` | Quelle, Job-ID und mögliche Dublette zu einer URL |
| POST | `/api/sources/import` | Anzeige laden und Felder vorschlagen (speichert nichts) |
| GET | `/api/postings` | Liste mit `q`, `status`, `source` (mehrfach), `sort`, `order`, `limit`, `offset` |
| POST | `/api/postings` | Stelle + Bewerbung anlegen (409 bei Dublette) |
| GET/PATCH | `/api/postings/{id}` | Detail / Teil-Update |
| POST | `/api/postings/{id}/archive` · `/restore` | Soft-Delete / Wiederherstellen |
| POST | `/api/applications/{id}/status` | Statuswechsel als Event (optional Notiz, Datum) |
| PATCH | `/api/applications/{id}` | Priorität, Kontakt, Nachfass-Datum |
| POST | `/api/applications/{id}/notes` | Notiz hinzufügen |
| GET | `/api/stats` | Zähler je Status/Quelle, Rücklaufquote |

Vollständig und interaktiv unter `/docs`.
