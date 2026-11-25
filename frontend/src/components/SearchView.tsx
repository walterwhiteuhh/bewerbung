import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CompanyLogo } from "./CompanyLogo";
import { FeatureChips } from "./Insights";
import { sortHits, type HitSort } from "../lib/sortHits";
import { PlaceHover } from "./PlaceCard";
import { RunHistory } from "./RunHistory";
import { useState, type FormEvent } from "react";

import { api } from "../api/client";
import { OFFER_TYPES, WORK_TIMES, type JobFeatures, type JobSource, type Listing, type OfferType, type SearchParams, type SearchProfile, type SearchRun, type WorkTime } from "../api/types";
import { formatDate, formatSalary } from "../lib/format";
import { OFFER_TYPE_LABEL, REMOTE_LABEL, SOURCE_LABEL, WORK_TIME_LABEL } from "../lib/labels";
import { MetaLine, SourceTag } from "./Badges";
import { useToast } from "./Toast";

const RADII = [0, 10, 25, 50, 100];

interface Props {
  onOpenPosting: (id: number) => void;
}

export function SearchView({ onOpenPosting }: Props) {
  const toast = useToast();
  const qc = useQueryClient();
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers, staleTime: 300_000 });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });

  const [form, setForm] = useState<SearchParams>({
    query: "",
    location: "",
    radius_km: 25,
    remote_only: false,
    work_times: [],
    offer_type: "arbeit",
    sources: [],
  });
  const [run, setRun] = useState<SearchRun | null>(null);
  // Gerade bearbeitete gespeicherte Suche (null = neue Suche)
  const [editing, setEditing] = useState<{ id: number; name: string } | null>(null);
  const [onlyNew, setOnlyNew] = useState(false);
  const [sort, setSort] = useState<HitSort>("rank");

  const available = (providers.data ?? []).filter((p) => p.available);
  const set = <K extends keyof SearchParams>(k: K, v: SearchParams[K]) => setForm((f) => ({ ...f, [k]: v }));

  const search = useMutation({
    mutationFn: (p: SearchParams) =>
      api.search({ ...p, location: p.location?.trim() || null, radius_km: p.location?.trim() ? p.radius_km : null }),
    onSuccess: (r) => {
      setRun(r);
      void qc.invalidateQueries({ queryKey: ["runs"] });
      r.errors.forEach((e) => toast(`${SOURCE_LABEL[e.source as JobSource] ?? e.source}: ${e.message}`, "error"));
    },
    onError: (e) => toast(e.message, "error"),
  });

  const profilePayload = (name: string) => ({
    name: name.trim() || [form.query, form.location, ...form.work_times.map((w) => WORK_TIME_LABEL[w])].filter(Boolean).join(" · "),
    query: form.query,
    location: form.location || null,
    radius_km: form.location ? form.radius_km : null,
    remote_only: form.remote_only,
    work_times: form.work_times,
    offer_type: form.offer_type,
    sources: form.sources,
  });

  const saveProfile = useMutation({
    mutationFn: () =>
      editing ? api.updateProfile(editing.id, profilePayload(editing.name)) : api.createProfile(profilePayload("")),
    onSuccess: () => {
      toast(editing ? "Gespeicherte Suche aktualisiert" : "Suche gespeichert");
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["profiles"] });
    },
    onError: (e) => toast(e.message, "error"),
  });

  const deleteProfile = useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: (_d, id) => {
      if (editing?.id === id) setEditing(null);
      void qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });

  function profileToParams(p: SearchProfile): SearchParams {
    return {
      query: p.query,
      location: p.location ?? "",
      radius_km: p.radius_km ?? 25,
      remote_only: p.remote_only,
      work_times: p.work_times ?? [],
      offer_type: p.offer_type ?? "arbeit",
      sources: p.sources,
    };
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (form.query.trim()) search.mutate(form);
  }

  function toggleWorkTime(w: WorkTime | null) {
    set("work_times", w === null ? [] : form.work_times.includes(w) ? form.work_times.filter((x) => x !== w) : [...form.work_times, w]);
  }

  function toggleSource(s: JobSource) {
    set("sources", form.sources.includes(s) ? form.sources.filter((x) => x !== s) : [...form.sources, s]);
  }

  function markSaved(listingId: number, postingId: number) {
    setRun((r) =>
      r && {
        ...r,
        hits: r.hits.map((h) => (h.listing.id === listingId ? { ...h, listing: { ...h.listing, posting_id: postingId } } : h)),
      },
    );
  }

  const hits = sortHits((run?.hits ?? []).filter((h) => !onlyNew || h.is_new), sort);

  return (
    <div className="search-view">
      <form className="search-form" onSubmit={submit}>
        <label className="field search-form__what">
          <span>Was</span>
          <input
            required
            placeholder="z. B. Data Scientist, Python"
            value={form.query}
            onChange={(e) => set("query", e.target.value)}
          />
        </label>
        <label className="field search-form__where">
          <span>Wo</span>
          <input placeholder="Ort oder PLZ" value={form.location ?? ""} onChange={(e) => set("location", e.target.value)} />
        </label>
        <label className="field search-form__radius">
          <span>Umkreis</span>
          <select
            value={form.radius_km ?? 0}
            onChange={(e) => set("radius_km", Number(e.target.value))}
            disabled={!form.location}
          >
            {RADII.map((r) => (
              <option key={r} value={r}>
                {r === 0 ? "nur Ort" : `${r} km`}
              </option>
            ))}
          </select>
        </label>

        <div className="search-form__opts search-form__kind" role="group" aria-label="Arbeitszeit">
          <span className="muted search-form__label">Arbeitszeit</span>
          <button type="button" className={`chip ${form.work_times.length === 0 ? "is-active" : ""}`} onClick={() => toggleWorkTime(null)}>
            Alle
          </button>
          {WORK_TIMES.map((w) => (
            <button
              key={w}
              type="button"
              className={`chip ${form.work_times.includes(w) ? "is-active" : ""}`}
              aria-pressed={form.work_times.includes(w)}
              onClick={() => toggleWorkTime(w)}
            >
              {WORK_TIME_LABEL[w]}
            </button>
          ))}
          <select
            className="search-form__offer"
            aria-label="Art des Angebots"
            value={form.offer_type}
            onChange={(e) => set("offer_type", e.target.value as OfferType)}
          >
            {OFFER_TYPES.map((o) => (
              <option key={o} value={o}>
                {OFFER_TYPE_LABEL[o]}
              </option>
            ))}
          </select>
        </div>

        <div className="search-form__opts">
          {(providers.data ?? []).map((p) => (
            <button
              key={p.source}
              type="button"
              className={`chip ${p.available && (form.sources.length === 0 || form.sources.includes(p.source)) ? "is-active" : ""}`}
              disabled={!p.available}
              title={p.reason ?? undefined}
              onClick={() => toggleSource(p.source)}
            >
              {SOURCE_LABEL[p.source] ?? p.label}
              {!p.available && <span className="chip__count">nicht eingerichtet</span>}
            </button>
          ))}
          <label className="toggle">
            <input type="checkbox" checked={form.remote_only} onChange={(e) => set("remote_only", e.target.checked)} />
            Nur Homeoffice
          </label>
        </div>

        {editing && (
          <label className="field search-form__editname">
            <span>Name der gespeicherten Suche</span>
            <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
          </label>
        )}
        <div className="search-form__actions">
          {editing && (
            <button type="button" className="btn btn--ghost" onClick={() => setEditing(null)}>
              Abbrechen
            </button>
          )}
          <button
            type="button"
            className={editing ? "btn" : "btn btn--ghost"}
            disabled={!form.query.trim() || saveProfile.isPending}
            onClick={() => saveProfile.mutate()}
          >
            {editing ? "Änderungen speichern" : "Suche speichern"}
          </button>
          <button type="submit" className="btn btn--primary" disabled={search.isPending || available.length === 0}>
            {search.isPending ? <span className="spinner spinner--light" aria-label="Sucht" /> : "Suchen"}
          </button>
        </div>
      </form>

      {(profiles.data?.length ?? 0) > 0 && (
        <div className="saved-searches">
          <span className="muted">Gespeichert:</span>
          {profiles.data!.map((p) => (
            <span key={p.id} className={`chip chip--split ${editing?.id === p.id ? "is-active" : ""}`}>
              <button
                type="button"
                title="Suche ausführen"
                onClick={() => {
                  const params = profileToParams(p);
                  setForm(params);
                  search.mutate({ ...params, profile_id: p.id });
                }}
              >
                {p.name}
              </button>
              <button
                type="button"
                aria-label={`${p.name} bearbeiten`}
                title="Bearbeiten"
                onClick={() => {
                  setForm(profileToParams(p));
                  setEditing({ id: p.id, name: p.name });
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                ✎
              </button>
              <button
                type="button"
                aria-label={`${p.name} löschen`}
                title="Löschen"
                onClick={() => {
                  if (window.confirm(`Gespeicherte Suche „${p.name}“ löschen?`)) deleteProfile.mutate(p.id);
                }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {run ? (
        <section className="results" aria-busy={search.isPending}>
          <div className="results__head">
            <span className="muted">
              {run.total_hits} Treffer, davon {run.new_hits} neu
            </span>
            <div className="results__tools">
              <select value={sort} onChange={(e) => setSort(e.target.value as HitSort)} aria-label="Sortierung">
                <option value="rank">Reihenfolge der Portale</option>
                <option value="match">Beste Passung</option>
                <option value="distance">Nächste zuerst</option>
                <option value="fresh">Neueste zuerst</option>
              </select>
              <label className="toggle">
                <input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} />
                Nur neue
              </label>
            </div>
          </div>
          {hits.length === 0 ? (
            <div className="empty">
              <p className="empty__title">Keine Treffer</p>
              <p>Versuch einen allgemeineren Begriff oder einen größeren Umkreis.</p>
            </div>
          ) : (
            <ul className="list list--results">
              {hits.map((h) => (
                <HitCard key={h.listing.id} listing={h.listing} features={h.features} isNew={h.is_new} onSaved={markSaved} onOpen={onOpenPosting} />
              ))}
            </ul>
          )}
        </section>
      ) : (
        <RunHistory
          onOpen={setRun}
          emptyHint={`Durchsuche ${available.map((p) => SOURCE_LABEL[p.source] ?? p.label).join(" und ") || "die Portale"} gleichzeitig. Treffer kannst du mit einem Klick merken.`}
        />
      )}
    </div>
  );
}


/** Sortierung nur in der Ansicht; fehlende Werte landen immer am Ende. */

function HitCard({
  listing: l,
  features,
  isNew,
  onSaved,
  onOpen,
}: {
  listing: Listing;
  features: JobFeatures | null;
  isNew: boolean;
  onSaved: (listingId: number, postingId: number) => void;
  onOpen: (postingId: number) => void;
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const save = useMutation({
    mutationFn: () => api.saveListing(l.id),
    onSuccess: (p) => {
      onSaved(l.id, p.id);
      toast("Gemerkt");
      void qc.invalidateQueries({ queryKey: ["postings"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (e) => toast(e.message, "error"),
  });
  const salary = l.salary_min || l.salary_max ? formatSalary(l.salary_min, l.salary_max, l.salary_currency ?? "EUR") : null;

  return (
    <li className="card card--hit">
      <div className="card__top">
        <SourceTag source={l.source} />
        {isNew && <span className="pill pill--new">neu</span>}
        {l.posted_at && <span className="muted">{formatDate(l.posted_at)}</span>}
      </div>
      <h3 className="card__title">{l.title}</h3>
      <p className="card__company">
        <CompanyLogo name={l.company_name} url={l.company_logo_url} />
        <span>{l.company_name ?? "Firma unbekannt"}</span>
      </p>
      <MetaLine
        lead={
          l.location || features?.city ? (
            <PlaceHover info={{ location: l.location, companyName: l.company_name, companyLogo: l.company_logo_url, features }}>
              {l.location ?? features?.city}
            </PlaceHover>
          ) : null
        }
        items={[l.remote_type !== "unknown" ? REMOTE_LABEL[l.remote_type] : null, l.employment_type, salary]} />
      {features && <FeatureChips features={features} />}
      {l.description && (
        <p className={`card__desc ${expanded ? "is-open" : ""}`} onClick={() => setExpanded((x) => !x)}>
          {l.description}
        </p>
      )}
      <div className="card__actions">
        {l.url && (
          <a className="btn" href={l.url} target="_blank" rel="noreferrer noopener">
            Anzeige ↗
          </a>
        )}
        {l.posting_id ? (
          <button type="button" className="btn" onClick={() => onOpen(l.posting_id!)}>
            Gemerkt, öffnen
          </button>
        ) : (
          <button type="button" className="btn btn--primary" onClick={() => save.mutate()} disabled={save.isPending}>
            Merken
          </button>
        )}
      </div>
    </li>
  );
}
