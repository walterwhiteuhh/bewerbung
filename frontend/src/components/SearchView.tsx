import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "../api/client";
import type { JobSource, Listing, SearchParams, SearchRun } from "../api/types";
import { formatDate, formatSalary, relativeTime } from "../lib/format";
import { REMOTE_LABEL, SOURCE_LABEL } from "../lib/labels";
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
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.searchRuns });

  const [form, setForm] = useState<SearchParams>({
    query: "",
    location: "",
    radius_km: 25,
    remote_only: false,
    sources: [],
  });
  const [run, setRun] = useState<SearchRun | null>(null);
  const [onlyNew, setOnlyNew] = useState(false);

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

  const saveProfile = useMutation({
    mutationFn: () =>
      api.createProfile({
        name: [form.query, form.location].filter(Boolean).join(" · "),
        query: form.query,
        location: form.location || null,
        radius_km: form.location ? form.radius_km : null,
        remote_only: form.remote_only,
        sources: form.sources,
      }),
    onSuccess: () => {
      toast("Suche gespeichert");
      void qc.invalidateQueries({ queryKey: ["profiles"] });
    },
    onError: (e) => toast(e.message, "error"),
  });

  const deleteProfile = useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["profiles"] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (form.query.trim()) search.mutate(form);
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

  const hits = (run?.hits ?? []).filter((h) => !onlyNew || h.is_new);

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

        <div className="search-form__actions">
          <button type="button" className="btn btn--ghost" disabled={!form.query.trim() || saveProfile.isPending} onClick={() => saveProfile.mutate()}>
            Suche speichern
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
            <span key={p.id} className="chip chip--split">
              <button
                type="button"
                onClick={() => {
                  const params = { query: p.query, location: p.location ?? "", radius_km: p.radius_km ?? 25, remote_only: p.remote_only, sources: p.sources };
                  setForm(params);
                  search.mutate({ ...params, profile_id: p.id });
                }}
              >
                {p.name}
              </button>
              <button type="button" aria-label={`${p.name} löschen`} onClick={() => deleteProfile.mutate(p.id)}>
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
            <label className="toggle">
              <input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} />
              Nur neue
            </label>
          </div>
          {hits.length === 0 ? (
            <div className="empty">
              <p className="empty__title">Keine Treffer</p>
              <p>Versuch einen allgemeineren Begriff oder einen größeren Umkreis.</p>
            </div>
          ) : (
            <ul className="list list--results">
              {hits.map((h) => (
                <HitCard key={h.listing.id} listing={h.listing} isNew={h.is_new} onSaved={markSaved} onOpen={onOpenPosting} />
              ))}
            </ul>
          )}
        </section>
      ) : (
        <section className="recent">
          <h3 className="section-title">Letzte Suchen</h3>
          {(runs.data?.length ?? 0) === 0 ? (
            <div className="empty">
              <p className="empty__title">Noch nicht gesucht</p>
              <p>Durchsuche {available.map((p) => SOURCE_LABEL[p.source] ?? p.label).join(" und ") || "die Portale"} gleichzeitig. Treffer kannst du mit einem Klick merken.</p>
            </div>
          ) : (
            <ul className="recent__list">
              {runs.data!.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    className="recent__item"
                    onClick={() => void api.searchRun(r.id).then(setRun).catch((e: Error) => toast(e.message, "error"))}
                  >
                    <strong>{r.query}</strong>
                    <span>{[r.location, r.remote_only ? "Homeoffice" : null].filter(Boolean).join(" · ") || "überall"}</span>
                    <span className="muted">
                      {r.total_hits} Treffer · {relativeTime(r.started_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function HitCard({
  listing: l,
  isNew,
  onSaved,
  onOpen,
}: {
  listing: Listing;
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
      <p className="card__company">{l.company_name ?? "Firma unbekannt"}</p>
      <MetaLine items={[l.location, l.remote_type !== "unknown" ? REMOTE_LABEL[l.remote_type] : null, l.employment_type, salary]} />
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
