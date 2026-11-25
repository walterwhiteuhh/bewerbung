import { useState } from "react";

import { usePostings } from "./api/hooks";
import { SOURCES, type ApplicationStatus, type JobSource, type PostingDetail as Posting, type PostingFilter, type SortField } from "./api/types";
import { Dialog } from "./components/Dialog";
import { ShipScene } from "./components/ShipScene";
import { EMPTY_EXTRA, FilterPanel, activeFilterCount } from "./components/FilterPanel";
import { PostingDetail } from "./components/PostingDetail";
import { PostingForm } from "./components/PostingForm";
import { PostingList } from "./components/PostingList";
import { DocumentsPanel } from "./components/Documents";
import { ProfileForm } from "./components/ProfileForm";
import { SearchView } from "./components/SearchView";
import { StatsBar } from "./components/StatsBar";
import { TagFilterBar } from "./components/TagInput";
import { SOURCE_LABEL } from "./lib/labels";
import { addUnique, sameTag, splitHashtags } from "./lib/tags";
import { useDebounced, useMediaQuery, useSelectedId, useView } from "./lib/useHashRoute";

const SORTS: { value: `${SortField}:${"asc" | "desc"}`; label: string }[] = [
  { value: "updated_at:desc", label: "Zuletzt bearbeitet" },
  { value: "created_at:desc", label: "Neueste zuerst" },
  { value: "status_changed_at:desc", label: "Letzter Statuswechsel" },
  { value: "priority:desc", label: "Priorität" },
  { value: "title:asc", label: "Titel A–Z" },
];

type ProfileTab = "angaben" | "unterlagen";
type FormState = { mode: "create" } | { mode: "edit"; posting: Posting } | null;

export function App() {
  const isWide = useMediaQuery("(min-width: 1024px)");
  const [selectedId, select] = useSelectedId();
  const [view, setView] = useView();
  const [extra, setExtra] = useState(EMPTY_EXTRA);
  const [showFilters, setShowFilters] = useState(false);
  const [form, setForm] = useState<FormState>(null);
  const [profileTab, setProfileTab] = useState<ProfileTab | null>(null);

  const [q, setQ] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [status, setStatus] = useState<ApplicationStatus[]>([]);
  const [source, setSource] = useState<JobSource | "">("");
  const [sort, setSort] = useState<(typeof SORTS)[number]["value"]>("updated_at:desc");

  const [sortField, order] = sort.split(":") as [SortField, "asc" | "desc"];
  const debouncedExtra = useDebounced(extra, 300);
  // "#python" im Suchfeld wirkt wie ein Klick auf den Hashtag, der Rest bleibt Freitext.
  const typed = splitHashtags(useDebounced(q));
  const activeTags = typed.tags.reduce(addUnique, tags);
  const filter: PostingFilter = {
    ...debouncedExtra,
    q: typed.text,
    tag: activeTags,
    status,
    source: source ? [source] : [],
    sort: sortField,
    order,
  };
  const { data, isLoading, isFetching } = usePostings(filter);
  const filtered = Boolean(filter.q || status.length || source || activeTags.length || activeFilterCount(extra));
  const toggleTag = (t: string) =>
    setTags((cur) => (cur.some((x) => sameTag(x, t)) ? cur.filter((x) => !sameTag(x, t)) : [...cur, t]));

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
  const profileButton = (
    <button type="button" className="btn btn--ghost topbar__profile" onClick={() => setProfileTab("angaben")}>
      Mein Profil
    </button>
  );
  const profileDialog = (
    <Dialog open={profileTab !== null} title="Mein Profil" onClose={() => setProfileTab(null)}>
      <nav className="tabs tabs--light profile-tabs" aria-label="Profil">
        <button type="button" className={profileTab === "angaben" ? "is-active" : ""} onClick={() => setProfileTab("angaben")}>
          Angaben
        </button>
        <button type="button" className={profileTab === "unterlagen" ? "is-active" : ""} onClick={() => setProfileTab("unterlagen")}>
          Unterlagen
        </button>
      </nav>
      {profileTab === "unterlagen" ? <DocumentsPanel /> : <ProfileForm onDone={() => setProfileTab(null)} />}
    </Dialog>
  );

  if (view === "search") {
    return (
      <div className="shell">
        <header className="topbar">
          <div className="topbar__inner topbar__inner--search">
            <Brand />
            {tabs}
            {profileButton}
          </div>
        </header>
        <div className="band band--search">
          <div className="band__inner">
            <h2 className="band__title">Neue Stellen finden</h2>
            <p className="band__lead">Durchsucht die angebundenen Jobbörsen auf einmal. Treffer, die du merkst, landen in deinen Stellen.</p>
          </div>
        </div>
        <div className="app">
          <SearchView onOpenPosting={select} />
        </div>
        {profileDialog}
      </div>
    );
  }

  return (
    <div className={`shell ${detailOpen ? "has-detail" : ""}`}>
      <header className="topbar">
        <div className="topbar__inner">
          <Brand />
          {tabs}
          <label className="search">
            <span className="sr-only">Suchen</span>
            <svg viewBox="0 0 24 24" aria-hidden>
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input type="search" placeholder="Titel, Firma, Ort oder #hashtag …" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          {profileButton}
          <button type="button" className="btn btn--primary topbar__new" onClick={() => setForm({ mode: "create" })}>
            Neue Stelle
          </button>
        </div>
      </header>

      <div className="band">
        <div className="band__inner">
          <StatsBar selected={status} onToggle={toggleStatus} />
        </div>
      </div>

      <div className="app">
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
          <TagFilterBar selected={activeTags} onToggle={toggleTag} />
          <PostingList
            items={data?.items ?? []}
            selectedId={selectedId}
            onSelect={select}
            loading={isLoading}
            filtered={filtered}
            onCreate={() => setForm({ mode: "create" })}
            activeTags={activeTags}
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
              onOpenProfile={(tab = "angaben") => setProfileTab(tab)}
            />
          ) : (
            <div className="empty empty--detail">
              <ShipScene />
              <p className="empty__title">Noch nichts an Deck</p>
              <p>Wähle links eine Stelle, um Status, Notizen und Verlauf zu sehen.</p>
            </div>
          )}
        </section>
      </main>
      </div>

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
      {profileDialog}
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="9" />
        <g fill="none" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="16" cy="8.2" r="2.6" />
          <path d="M16 10.8v14.4M11 14.5h10M7.5 18.5c.6 4.4 4.2 6.9 8.5 6.9s7.9-2.5 8.5-6.9M5.8 20.4l1.7-1.9 2 1.6M26.2 20.4l-1.7-1.9-2 1.6" />
        </g>
      </svg>
      <div className="brand__text">
        <h1 aria-label="Anheuern">
          An<span className="brand__accent">heuern</span>
        </h1>
        <span className="brand__tag">Kurs auf den nächsten Job</span>
      </div>
    </div>
  );
}
