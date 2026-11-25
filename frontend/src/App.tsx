import { useState } from "react";

import { usePostings } from "./api/hooks";
import { SOURCES, type ApplicationStatus, type JobSource, type PostingDetail as Posting, type PostingFilter, type SortField } from "./api/types";
import { Dialog } from "./components/Dialog";
import { EMPTY_EXTRA, FilterPanel, activeFilterCount } from "./components/FilterPanel";
import { PostingDetail } from "./components/PostingDetail";
import { PostingForm } from "./components/PostingForm";
import { PostingList } from "./components/PostingList";
import { SearchView } from "./components/SearchView";
import { StatsBar } from "./components/StatsBar";
import { SOURCE_LABEL } from "./lib/labels";
import { useDebounced, useMediaQuery, useSelectedId, useView } from "./lib/useHashRoute";

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
  const [view, setView] = useView();
  const [extra, setExtra] = useState(EMPTY_EXTRA);
  const [showFilters, setShowFilters] = useState(false);
  const [form, setForm] = useState<FormState>(null);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus[]>([]);
  const [source, setSource] = useState<JobSource | "">("");
  const [sort, setSort] = useState<(typeof SORTS)[number]["value"]>("updated_at:desc");

  const [sortField, order] = sort.split(":") as [SortField, "asc" | "desc"];
  const debouncedExtra = useDebounced(extra, 300);
  const filter: PostingFilter = {
    ...debouncedExtra,
    q: useDebounced(q),
    status,
    source: source ? [source] : [],
    sort: sortField,
    order,
  };
  const { data, isLoading, isFetching } = usePostings(filter);
  const filtered = Boolean(filter.q || status.length || source || activeFilterCount(extra));

  const toggleStatus = (s: ApplicationStatus | null) =>
    setStatus((cur) => (s === null ? [] : cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const openFromForm = (id: number) => {
    setForm(null);
    select(id);
  };

  const detailOpen = selectedId !== null;
  const tabs = (
    <nav className="tabs" aria-label="Ansicht">
      <button type="button" className={view === "list" ? "is-active" : ""} aria-current={view === "list"} onClick={() => setView("list")}>
        Meine Stellen
      </button>
      <button type="button" className={view === "search" ? "is-active" : ""} aria-current={view === "search"} onClick={() => setView("search")}>
        Suche in Portalen
      </button>
    </nav>
  );

  if (view === "search") {
    return (
      <div className="app">
        <header className="topbar topbar--search">
          <div className="brand">
            <span className="brand__mark" aria-hidden />
            <h1>Bewerbungen</h1>
          </div>
          {tabs}
        </header>
        <SearchView onOpenPosting={select} />
      </div>
    );
  }

  return (
    <div className={`app ${detailOpen ? "has-detail" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden />
          <h1>Bewerbungen</h1>
        </div>
        {tabs}
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
            <button
              type="button"
              className={`btn btn--small ${showFilters || activeFilterCount(extra) ? "is-active" : ""}`}
              aria-expanded={showFilters}
              onClick={() => setShowFilters((x) => !x)}
            >
              Filter{activeFilterCount(extra) ? ` (${activeFilterCount(extra)})` : ""}
            </button>
            <span className="muted filters__count">
              {data ? `${data.total} ${data.total === 1 ? "Stelle" : "Stellen"}` : ""}
              {isFetching && !isLoading ? " …" : ""}
            </span>
          </div>
          {showFilters && <FilterPanel value={extra} onChange={setExtra} />}
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
