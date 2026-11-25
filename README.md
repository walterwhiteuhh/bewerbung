# Anheuern

_Kurs auf den nächsten Job._ Stellenanzeigen aus mehreren Portalen finden, Bewerbungen steuern und Anschreiben erstellen, alles an einem Ort.
(Python-Paket und Ordner heißen weiterhin `bewerbung`.)
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
cd frontend && npm test                  # Vitest: Formatierung, Sortierung, Kartenmathematik, Komponenten
cd frontend && npm run build && npm run test:e2e   # Playwright: Layout von 320 px bis 4K
```

GitHub Actions (`.github/workflows/ci.yml`) führt alles bei jedem Pull Request aus.

### Responsivität

Ein Layout für alle Geräte, mobil zuerst. Die Playwright-Tests (`frontend/e2e/responsive.spec.ts`)
öffnen Liste, Detail, Suche, Info-Karte und Dialoge in zehn Breiten von 320 px (iPhone SE) bis
3840 px (4K) und schlagen fehl, sobald

- die Seite seitlich scrollt oder ein Element aus dem Bild ragt,
- auf Touch-Geräten ein Bedienelement kleiner als 32 px ist,
- die Info-Karte oder ein Dialog den Bildschirm verlässt (unter 640 px wird die Karte zum Bottom-Sheet),
- auf großen Bildschirmen Schrift und Inhaltsbreite nicht mitwachsen (17/20/24 px ab 1800/2400/3200 px).

Der Testserver `tests/e2e/server.py` startet die App mit Temp-Datenbank und Fake-Portalen, enthält
bewusst überlange Titel und Firmennamen und braucht kein Netzwerk. Lange Wörter brechen über
`overflow-wrap: anywhere`, Grid-Spalten verwenden `minmax(0, 1fr)`, damit ein einzelner
`nowrap`-Text nicht die ganze Spalte aufbläht.

Leere Ansichten zeigen ein kleines SVG-Segelschiff auf bewegter See (`ShipScene.tsx`): reine
CSS-Transforms, keine Bilder, kein JavaScript pro Frame, unter 2 KB. Bei „Bewegung reduzieren“
im System steht es still.

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
| `tags` / `posting_tags` | Hashtags. `tags.key` ist der normalisierte Name ("Python" = "python"); Zuordnungen werden beim Entfernen mit `removed_at` beendet statt gelöscht, `origin` sagt, ob sie von Hand oder aus einer Notiz (`#tag`) kamen |
| `notes` | Notizen pro Bewerbung |
| `applicant_profiles` | Eigenes Profil (eine Zeile) |
| `documents` | Hochgeladene Unterlagen: Art, SHA-256, ausgelesener Text mit Extraktor-Version, Haupt-Lebenslauf; Soft-Delete |
| `posting_documents` | Welche Unterlagen zu welcher Bewerbung gehören; Entfernen setzt `detached_at` |
| `cover_letters` | Anschreiben-Fassungen je Stelle: `body_generated` bleibt unverändert, `body` ist editierbar; `input_snapshot`, `generator`, `model`, `prompt_version`, Tokens und Dauer für spätere Auswertung |
| `listings` | Anzeige je Portal (Rohsicht); `posting_id` NULL = Suchtreffer, sonst verknüpfte Stelle |
| `search_profiles` | Gespeicherte Suchen |
| `search_runs` / `search_hits` | Append-only Protokoll jedes Suchlaufs mit Treffern und Rang (Basis für späteres Relevanz-Ranking: gezeigt → gemerkt) |

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

### Suche in Portalen

Der Reiter „Suche in Portalen“ fragt offizielle Such-Schnittstellen parallel ab. Filter für die
Arbeitszeit (Vollzeit, Teilzeit, Minijob, Schicht/Nacht/Wochenende, mehrere = ODER) und die Art
des Angebots (Arbeitsstelle, Ausbildung, Praktikum, Selbstständigkeit) gehen bei der
Arbeitsagentur direkt an die API; Adzuna kennt nur Voll-/Teilzeit, dort wird „Minijob“ als
Suchwort ergänzt.

| Quelle | Einrichtung |
|---|---|
| Bundesagentur für Arbeit | keine (öffentliche Jobsuche-API) |
| Adzuna (bündelt viele Portale) | kostenlosen Key auf https://developer.adzuna.com holen, dann in `.env`: `BEWERBUNG_ADZUNA_APP_ID=...` und `BEWERBUNG_ADZUNA_APP_KEY=...` |
| Jooble (bündelt sehr viele Jobbörsen und Karriereseiten) | kostenlosen Key auf https://jooble.org/api/about anfordern, dann in `.env`: `BEWERBUNG_JOOBLE_API_KEY=...` |
| Arbeitnow (Deutschland/Europa, oft englischsprachig) | keine; die API hat keine Suchfunktion, die App lädt die neuesten ~300 Anzeigen und filtert selbst |
| Remotive (nur Remote-Stellen) | keine; nur Anzeigen, die aus Deutschland/Europa besetzt werden dürfen |

LinkedIn, StepStone, Indeed und XING bieten keine öffentliche Such-API und blockieren automatische
Abrufe. Deren Anzeigen kommen über Jooble/Adzuna (die viele davon bündeln) oder per Link-Import.

Treffer werden als `listings` gespeichert (`first_seen_at`/`last_seen_at`, `content_hash`),
jeder Lauf mit Rang in `search_runs`/`search_hits`. „Merken“ legt Stelle und Bewerbung an und
verknüpft das Listing. Suchen lassen sich als Profil speichern.

### Anschreiben

In jeder Stelle öffnet „Anschreiben erstellen“ eine Werkstatt. Portal (z. B. StepStone, LinkedIn),
Firma, Hashtags, Beschreibung und die Skills aus „Mein Profil“, die zur Anzeige passen, werden
automatisch erkannt und an den Generator gegeben. Ton und Länge sind wählbar, jede Fassung wird
versioniert gespeichert (Original und bearbeiteter Text getrennt, plus Eingaben-Snapshot,
Modell, Prompt-Version und Tokens). Eine Fassung pro Stelle kann als „final“ markiert werden.

Für KI-Texte einen oder mehrere Keys in die `.env` im Projektordner eintragen:

| Anbieter | Eintrag in `.env` | Modell ändern (optional) |
|---|---|---|
| Claude (Anthropic) | `ANTHROPIC_API_KEY=...` | `BEWERBUNG_COVER_LETTER_MODEL=claude-opus-5-5` |
| ChatGPT (OpenAI) | `OPENAI_API_KEY=...` | `BEWERBUNG_OPENAI_MODEL=gpt-5` |
| Gemini (Google AI Studio) | `GEMINI_API_KEY=...` | `BEWERBUNG_GEMINI_MODEL=gemini-2.5-pro` |

Danach die App neu starten. „Automatisch“ nimmt den ersten Anbieter mit Key (Reihenfolge wie oben),
im Dialog lässt sich jeder einzeln wählen. Ohne Key entsteht ein Entwurf aus einer Vorlage.
Hinweis: Beim Erstellen gehen Stellendaten und Profil an den gewählten Anbieter.

### Unterlagen

Unter „Mein Profil → Unterlagen“ lassen sich Lebenslauf, Zeugnisse, Zertifikate usw. hochladen
(PDF, Word .docx, Text, PNG/JPG, bis 15 MB, per Drag-and-drop). Der Dateityp wird am Inhalt
erkannt, nicht an der Endung. Text aus PDF und Word wird ausgelesen; der Haupt-Lebenslauf fließt
automatisch in die Anschreiben ein, falls im Profil kein Lebenslauf-Text steht („Text ins Profil“
übernimmt ihn dauerhaft). In jeder Stelle markierst du, welche Unterlagen du mitschickst.

Die Dateien liegen inhaltsadressiert (SHA-256) im Ordner `documents` neben der Datenbank,
also unter `data/documents/`. Ein Backup von `data/` enthält damit alles.

### Firmenlogos

Logos kommen aus den Daten, die ohnehin geladen werden: `hiringOrganization.logo` im JSON-LD
importierter Anzeigen und Logo-Felder der Such-APIs (z. B. Remotive). Sie landen in
`listings.company_logo_url` und, sobald eine Stelle gemerkt wird, in `companies.logo_url`.
Arbeitsagentur-Logos brauchen den API-Key-Header; deshalb holt der Server sie über
`/api/logos/arbeitsagentur/{hash}` einmal ab und legt sie in `data/logos/` ab (fehlende Logos
werden eine Woche lang nicht erneut angefragt, SVG wird nicht angenommen). Ohne Logo zeigt die
Oberfläche die Initialen der Firma. Migration 0008 trägt Logos aus vorhandenen Rohdaten nach.

Liefert die Quelle kein Logo (z. B. die Arbeitsagentur, deren Logo-Endpunkt mit 403 antwortet),
kann in der Stelle unter „Firma“ die Website eingetragen werden. Die App lädt dann die Startseite,
wählt `apple-touch-icon` vor SVG- und PNG-Favicons (Rückfall `/favicon.ico`) und speichert das
Bild inhaltsadressiert in `data/logos/` (`/api/logos/files/<sha256>.<ext>`). Interne Adressen
werden wie beim Import abgelehnt, SVG wird mit `Content-Security-Policy: sandbox` ausgeliefert.
Website, Branche und Firmensitz gelten für alle Stellen der Firma (`PATCH /api/companies/{id}`,
`POST /api/companies/{id}/logo`). Beim Import wird `hiringOrganization.sameAs`/`url` als Website
übernommen, sofern es keine Portal-Adresse ist.

### Zusammenhänge und Merkmale

Jede Anzeige wird beim Speichern einer Firma (`listings.company_id`, gleicher Schlüssel wie
`companies.name_key`) und einem Titel-Schlüssel ohne Gender-Zusätze (`title_key`) zugeordnet;
Ort, PLZ und Koordinaten kommen aus den Rohdaten (Arbeitsagentur-Lokationen, JSON-LD `geo`).
Daraus berechnet `services/insights.py` zur Laufzeit:

| Merkmal | Herleitung |
|---|---|
| Entfernung | Luftlinie Wohnort ↔ Anzeige; ohne Koordinaten Median-Stadtmitte aus anderen Anzeigen („ca.“) |
| Wohnort | PLZ/Ort aus „Mein Profil“, Koordinaten aus bekannten Anzeigen (kein Geocoding-Dienst) |
| Passung | Anteil der Skills der Anzeige, die in Profil-Skills oder Lebenslauf vorkommen |
| Portale / neu ausgeschrieben | gleiche Firma + gleicher Titel-Schlüssel auf mehreren Portalen bzw. unter neuer ID |
| Firmenaktivität | Anzeigen der Firma (aktiv = 14 Tage gesehen), eigene Bewerbungen und Absagen dort |
| Ähnlichkeit | gewichtete Jaccard-Ähnlichkeit von Titel-Wörtern (60 %) und Skills (40 %) |

Suchtreffer tragen die Merkmale (`features`) und lassen sich nach Passung, Entfernung und Alter
sortieren; jede Stelle zeigt „Zusammenhänge“ (`GET /api/postings/{id}/insights`).
`GET /api/insights/listings.csv` exportiert alle Anzeigen mit denselben Merkmalen und dem
Bewerbungsstatus als Label, als Ausgangspunkt für ein späteres Ranking-Modell.

**Info-Karte am Ort:** Beim Überfahren (Touch: Tippen) des Orts auf Treffer- und Stellenkarten
erscheint eine Karte mit Minikarte (OpenStreetMap-Kacheln, Wohnort und Stelle), Entfernung,
Firmenaktivität, Website und Social-Media-Profilen sowie Links „Karte öffnen“ und „Route“.
Die Kacheln lädt der Browser direkt von `tile.openstreetmap.org`; ohne Internet bleibt die Karte
schraffiert, Markierungen und Entfernung stimmen trotzdem.

**Social-Media-Profile** (`companies.social_links`, `domain/socials.py`): LinkedIn, XING, kununu,
Instagram, Facebook, YouTube, X, TikTok und GitHub werden aus JSON-LD `sameAs` der Anzeigen und
beim Laden von der Firmen-Website aus deren Links übernommen (Teilen-Links und einzelne Beiträge
zählen nicht) und lassen sich im Firmenbereich von Hand pflegen.

**Arbeitgeber-Bewertung** (`company_ratings`, append-only; `domain/ratings.py`): Je Portal
(kununu, Glassdoor, Indeed, Google, andere) werden Wert, Skala und Anzahl der Bewertungen im
Firmenbereich erfasst; die Portale sperren automatische Abrufe per Bot-Prüfung, daher von Hand
mit Direktlink zur Suche. Alle Werte werden auf 5 Sterne umgerechnet; der Gesamtwert ist das
arithmetische Mittel der Portale mit mindestens 10 Bewertungen (ungewichtet, damit kein Portal
dominiert). Er erscheint in Stelle, Info-Karte, als Merkmal und im CSV-Export
(`employer_rating*`; `employer_rating_observed_at` erlaubt, spätere Werte beim Training
auszuschließen).

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
| GET | `/api/tags` | Alle Hashtags mit Anzahl der Stellen; Filter in `/api/postings?tag=python&tag=remote` (UND) |
| GET | `/api/stats` | Zähler je Status/Quelle, Rücklaufquote |
| GET | `/api/search/providers` | Verfügbare Such-Quellen |
| POST | `/api/search` | Live-Suche über Portale |
| GET | `/api/search/runs` · `/runs/{id}` | Suchhistorie |
| GET/POST · PUT/DELETE `/{id}` | `/api/search/profiles` | Gespeicherte Suchen anlegen, bearbeiten, löschen |
| DELETE | `/api/search/runs/{id}` · `/api/search/runs` | Suche aus „Letzte Suchen“ entfernen / Verlauf leeren (nur ausgeblendet, Treffer-Historie bleibt) |
| POST | `/api/listings/{id}/save` | Treffer merken |
| GET/PUT | `/api/profile` | Eigenes Profil (Grundlage der Anschreiben) |
| GET | `/api/letters/generators` | Claude, ChatGPT, Gemini, Vorlage und ob ein Key da ist |
| GET | `/api/postings/{id}/letter-context` | Erkanntes Portal, Hashtags, passende Skills |
| GET/POST | `/api/postings/{id}/letters` | Fassungen auflisten / neue erzeugen |
| PATCH | `/api/letters/{id}` | Text bearbeiten, als final markieren |
| GET/POST | `/api/documents` | Unterlagen auflisten / hochladen (multipart, 409 bei Dublette) |
| GET | `/api/documents/{id}/file` | Datei ansehen (`?download=true` zum Herunterladen) |
| PATCH | `/api/documents/{id}` · POST `/archive` · `/use-as-cv` | Art/Titel/Haupt-CV ändern, archivieren, Text ins Profil |
| GET/PUT | `/api/postings/{id}/documents` | Unterlagen einer Bewerbung |

Vollständig und interaktiv unter `/docs`.
