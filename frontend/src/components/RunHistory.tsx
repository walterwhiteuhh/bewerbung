/**
 * „Letzte Suchen“: nach Tagen gruppiert, nach Zeitraum und Text filterbar, komplett oder
 * teilweise (Auswahl, Tag, Alter) entfernbar. Entfernt heißt in der DB: `hidden_at` wird
 * gesetzt, die Läufe samt Treffern bleiben für spätere Auswertungen erhalten.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import { WORK_TIME_LABEL } from "../lib/labels";
import { relativeTime } from "../lib/format";
import { groupRuns, olderThan, periodRange, rangeParams, type Period, type Range } from "../lib/runHistory";
import { useDebounced } from "../lib/useHashRoute";
import type { SearchRun, SearchRunSummary } from "../api/types";
import { useToast } from "./Toast";

const PERIODS: { value: Period; label: string }[] = [
  { value: "all", label: "Alle" },
  { value: "today", label: "Heute" },
  { value: "7d", label: "7 Tage" },
  { value: "30d", label: "30 Tage" },
];

interface Props {
  onOpen: (run: SearchRun) => void;
  emptyHint: string;
}

export function RunHistory({ onOpen, emptyHint }: Props) {
  const toast = useToast();
  const qc = useQueryClient();
  const [period, setPeriod] = useState<Period>("all");
  const [text, setText] = useState("");
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const q = useDebounced(text.trim());
  const range = periodRange(period);
  const filtered = period !== "all" || q !== "";

  const runs = useQuery({
    queryKey: ["runs", period, q, new Date().toDateString()],
    queryFn: () => api.searchRuns({ ...rangeParams(range), q: q || undefined }),
  });
  const items = runs.data ?? [];
  const groups = groupRuns(items);

  const clear = useMutation({
    mutationFn: api.clearRuns,
    onSuccess: ({ hidden }) => {
      toast(hidden === 1 ? "1 Suche entfernt" : `${hidden} Suchen entfernt`);
      setSelected([]);
      setSelecting(false);
      void qc.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (e) => toast(e.message, "error"),
  });

  const remove = (what: string, params: Parameters<typeof api.clearRuns>[0]) => {
    if (window.confirm(`${what} aus „Letzte Suchen“ entfernen? Die Treffer bleiben für die Auswertung gespeichert.`)) clear.mutate(params);
  };
  const removeRange = (what: string, r: Range) => remove(what, rangeParams(r));
  const toggle = (id: number) => setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  const open = (r: SearchRunSummary) => api.searchRun(r.id).then(onOpen).catch((e: Error) => toast(e.message, "error"));

  return (
    <section className="recent">
      <div className="recent__head">
        <h3 className="section-title">Letzte Suchen</h3>
        <div className="recent__tools">
          {items.length > 0 && (
            <button
              type="button"
              className={`btn btn--small btn--ghost ${selecting ? "is-active" : ""}`}
              aria-pressed={selecting}
              onClick={() => {
                setSelecting((s) => !s);
                setSelected([]);
              }}
            >
              Auswählen
            </button>
          )}
          <details className="menu">
            <summary className="btn btn--small btn--ghost">Löschen ▾</summary>
            <div className="menu__list" role="menu" onClick={(e) => e.currentTarget.parentElement?.removeAttribute("open")}>
              <button type="button" role="menuitem" onClick={() => removeRange("Suchen älter als 7 Tage", olderThan(7))}>
                Älter als 7 Tage
              </button>
              <button type="button" role="menuitem" onClick={() => removeRange("Suchen älter als 30 Tage", olderThan(30))}>
                Älter als 30 Tage
              </button>
              {filtered && items.length > 0 && (
                <button type="button" role="menuitem" onClick={() => remove("Die angezeigten Suchen", { ids: items.map((r) => r.id) })}>
                  Angezeigte ({items.length})
                </button>
              )}
              <button type="button" role="menuitem" className="menu__danger" onClick={() => remove("Alle Suchen", {})}>
                Alles löschen
              </button>
            </div>
          </details>
        </div>
      </div>

      <div className="recent__filters">
        <div className="seg" role="group" aria-label="Zeitraum">
          {PERIODS.map((p) => (
            <button key={p.value} type="button" className={period === p.value ? "is-active" : ""} aria-pressed={period === p.value} onClick={() => setPeriod(p.value)}>
              {p.label}
            </button>
          ))}
        </div>
        <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Verlauf durchsuchen …" aria-label="Verlauf durchsuchen" />
      </div>

      {selecting && (
        <div className="recent__bar" role="status">
          <span>{selected.length} ausgewählt</span>
          <button type="button" className="btn btn--small" onClick={() => setSelected(selected.length === items.length ? [] : items.map((r) => r.id))}>
            {selected.length === items.length ? "Keine" : "Alle"}
          </button>
          <button type="button" className="btn btn--small btn--primary" disabled={!selected.length || clear.isPending} onClick={() => remove(`${selected.length} Suchen`, { ids: selected })}>
            Entfernen
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <div className="empty">
          <p className="empty__title">{filtered ? "Keine Suche gefunden" : "Bereit zum Auslaufen"}</p>
          <p>{filtered ? "Ändere Zeitraum oder Suchtext." : emptyHint}</p>
        </div>
      ) : (
        groups.map((g) => (
          <div key={g.key} className="recent__group">
            <div className="recent__day">
              <h4>{g.label}</h4>
              <button type="button" className="btn btn--small btn--ghost" onClick={() => remove(`Alle Suchen vom Tag „${g.label}“`, { ids: g.runs.map((r) => r.id) })}>
                Tag leeren
              </button>
            </div>
            <ul className="recent__list">
              {g.runs.map((r) => (
                <li key={r.id} className="recent__row">
                  {selecting && (
                    <input type="checkbox" className="recent__check" checked={selected.includes(r.id)} onChange={() => toggle(r.id)} aria-label={`Suche „${r.query}“ auswählen`} />
                  )}
                  <button type="button" className="recent__item" onClick={() => (selecting ? toggle(r.id) : void open(r))}>
                    <strong>{r.query}</strong>
                    <span>
                      {[r.location, r.remote_only ? "Homeoffice" : null, ...(r.work_times ?? []).map((w) => WORK_TIME_LABEL[w])].filter(Boolean).join(" · ") || "überall"}
                    </span>
                    <span className="muted">
                      {r.total_hits} Treffer · {relativeTime(r.started_at)}
                    </span>
                  </button>
                  {!selecting && (
                    <button type="button" className="icon-btn recent__delete" aria-label={`Suche „${r.query}“ aus dem Verlauf löschen`} title="Aus dem Verlauf löschen" onClick={() => clear.mutate({ ids: [r.id] })}>
                      ✕
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
