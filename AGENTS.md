# AGENTS.md

Regeln für alle Coding-Agents in diesem Repository (Anheuern).

- **Basisregeln** (Stack, Architektur, maritimes Design, Responsive, Android/Capacitor, Datenregeln): [`docs/leitfaden-maritime-webapps.md`](docs/leitfaden-maritime-webapps.md). Das ist eine Kopie des übergeordneten Leitfadens „Responsive Webapps, maritim“; nicht hier ändern.
- **Projektspezifisches und Abweichungen** (npm statt pnpm, SQLite, flache Frontend-Struktur, kein Tailwind): [`CLAUDE.md`](CLAUDE.md), Abschnitt „Abweichungen vom Leitfaden“. Bei Widerspruch gilt `CLAUDE.md`.
- Funktionen, Datenmodell, API: [`README.md`](README.md).

## Setup
- Backend: [uv](https://docs.astral.sh/uv/), `uv sync`. Frontend: Node.js 20+, `npm install` in `frontend/`.

## Qualitätsschranken (müssen grün sein)
1. `uv run pytest`, `uv run ruff check src tests`, `uv run mypy src`
2. `cd frontend && npm run typecheck && npm test`
3. Bei UI-Änderungen zusätzlich `npm run build && npm run test:e2e` (Responsive-Tests)

## Pull Requests
- Kleine, thematisch geschlossene Änderungen mit Was/Warum.
- Tests für neue Logik; UI-Änderungen mit Screenshot (mobil + Desktop).

## Grenzen
- Keine Änderungen an CI, Lizenz oder Secrets ohne Rückfrage; `.env` nicht anfassen.
- Keine neuen Laufzeit-Abhängigkeiten ohne Begründung.
- Keine destruktiven Datenänderungen: Historie (Events, `raw_payload`) bleibt erhalten.
