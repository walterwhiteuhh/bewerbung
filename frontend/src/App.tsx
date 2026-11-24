import { useState } from "react";

import { usePostings } from "./api/hooks";
import { SOURCES, type ApplicationStatus, type JobSource, type PostingDetail as Posting, type PostingFilter, type SortField } from "./api/types";
import { Dialog } from "./components/Dialog";
import { PostingDetail } from "./components/PostingDetail";
import { PostingForm } from "./components/PostingForm";
import { PostingList } from "./components/PostingList";
import { StatsBar } from "./components/StatsBar";
import { SOURCE_LABEL } from "./lib/labels";
import { useDebounced, useMediaQuery, useSelectedId } from "./lib/useHashRoute";

const SORTS: { value: `${SortField}:${"asc" | "desc"}`; label: string }[] = [
  { value: "updated_at:desc", label: "Zuletzt bearbeitet" },
  { value: "created_at:desc", label: "Neueste zuerst" },
  { value: "status_changed_at:desc", label: "Letzter Statuswechsel" },
  { value: "priority:desc", label: "Priorität" },
  { value: "title:asc", label: "Titel A–Z" },
];

type FormState = { mode: "create" } | { mode: "edit"; posting: Posting } | null;

export function App() {
  const isWide = useMediaQuery("(min-width: 1024px)");
  const [selectedId, select] = useSelectedId();
  const [form, setForm] = useState<FormState>(null);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus[]>([]);
  const [source, setSource] = useState<JobSource | "">("");
  const [sort, setSort] = useState<(typeof SORTS)[number]["value"]>("updated_at:desc");

  const [sortField, order] = sort.split(":") as [SortField, "asc" | "desc"];
  const filter: PostingFilter = {
    q: useDebounced(q),
    status,
    source: source ? [source] : [],
    sort: sortField,
    order,
  };
  const { data, isLoading, isFetching } = usePostings(filter);
  const filtered = Boolean(filter.q || status.length || source);

  const toggleStatus = (s: ApplicationStatus | null) =>
    setStatus((cur) => (s === null ? [] : cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const openFromForm = (id: number) => {
    setForm(null);
    select(id);
  };

  const detailOpen = selectedId !== null;

  return (
    <div className={`app ${detailOpen ? "has-detail" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden />
          <h1>Bewerbungen</h1>
        </div>
        <label className="search">
          <span className="sr-only">Suchen</span>
          <svg viewBox="0 0 24 24" aria-hidden>
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input type="search" placeholder="Titel, Firma, Ort …" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <button type="button" className="btn btn--primary topbar__new" onClick={() => setForm({ mode: "create" })}>
          + Neue Stelle
        </button>
      </header>

      <StatsBar selected={status} onToggle={toggleStatus} />

      <main className="layout">
        <section className="pane pane--list" aria-label="Stellen">
          <div className="filters">
            <select value={source} onChange={(e) => setSource(e.target.value as JobSource | "")} aria-label="Quelle">
              <option value="">Alle Quellen</option>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABEL[s]}
                </option>
              ))}
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sortierung">
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <span className="muted filters__count">
              {data ? `${data.total} ${data.total === 1 ? "Stelle" : "Stellen"}` : ""}
              {isFetching && !isLoading ? " …" : ""}
            </span>
          </div>
          <PostingList
            items={data?.items ?? []}
            selectedId={selectedId}
            onSelect={select}
            loading={isLoading}
            filtered={filtered}
            onCreate={() => setForm({ mode: "create" })}
          />
        </section>

        <section className="pane pane--detail" aria-label="Details">
          {selectedId !== null ? (
            <PostingDetail
              key={selectedId}
              id={selectedId}
              onClose={() => select(null)}
              onEdit={(posting) => setForm({ mode: "edit", posting })}
              showClose={!isWide}
            />
          ) : (
            <div className="empty empty--detail">
              <p className="empty__title">Keine Stelle ausgewählt</p>
              <p>Wähle links eine Stelle, um Status, Notizen und Verlauf zu sehen.</p>
            </div>
          )}
        </section>
      </main>

      <button type="button" className="fab" onClick={() => setForm({ mode: "create" })} aria-label="Neue Stelle">
        +
      </button>

      <Dialog
        open={form !== null}
        title={form?.mode === "edit" ? "Stelle bearbeiten" : "Neue Stelle"}
        onClose={() => setForm(null)}
      >
        {form && (
          <PostingForm
            initial={form.mode === "edit" ? form.posting : undefined}
            onDone={openFromForm}
            onOpenExisting={openFromForm}
          />
        )}
      </Dialog>
    </div>
  );
}
