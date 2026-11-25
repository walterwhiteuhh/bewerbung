import { useState } from "react";
import { api } from "../api/client";
import { useMutate } from "../api/hooks";
import type { Company, EmployerRating, RatingSource } from "../api/types";
import { formatDate } from "../lib/format";
import { useToast } from "./Toast";

export const RATING_SOURCE_LABEL: Record<RatingSource, string> = {
  kununu: "kununu",
  glassdoor: "Glassdoor",
  indeed: "Indeed",
  google: "Google",
  other: "Andere",
};

const num = (x: number, digits = 1) => x.toFixed(digits).replace(".", ",");

/** Suche auf dem Portal, damit Wert und Anzahl schnell abgelesen werden können. */
function portalLink(source: RatingSource, company: Company): string | null {
  const q = encodeURIComponent(company.name);
  switch (source) {
    case "kununu":
      return company.social_links.kununu ?? `https://www.kununu.com/de/search#/?q=${q}`;
    case "glassdoor":
      return `https://www.glassdoor.de/Search/results.htm?keyword=${q}`;
    case "indeed":
      return `https://de.indeed.com/companies/search?q=${q}`;
    case "google":
      return `https://www.google.com/search?q=${q}+Arbeitgeber+Bewertungen`;
    default:
      return null;
  }
}

function Stars({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, (value / 5) * 100));
  return (
    <span className="stars" aria-hidden>
      <span className="stars__fill" style={{ width: `${pct}%` }}>★★★★★</span>★★★★★
    </span>
  );
}

const tone = (mean: number) => (mean >= 4 ? "good" : mean < 3 ? "warn" : "");

/** Kompakte Anzeige: „★ 4,1 aus 2 Portalen“ oder Hinweis auf zu wenige Bewertungen. */
export function RatingBadge({ rating, compact = false }: { rating: EmployerRating | null | undefined; compact?: boolean }) {
  if (!rating) return null;
  if (rating.mean === null) {
    return compact ? null : <span className="muted rating-note">Zu wenige Bewertungen für einen Mittelwert (mind. {rating.min_reviews} je Portal)</span>;
  }
  const title = rating.current
    .filter((c) => rating.sources.includes(c.source))
    .map((c) => `${RATING_SOURCE_LABEL[c.source]}: ${num(c.rating)} (${c.review_count} Bewertungen)`)
    .join("\n");
  return (
    <span className={`rating ${tone(rating.mean)}`} title={title}>
      <Stars value={rating.mean} />
      <strong>{num(rating.mean)}</strong>
      {!compact && (
        <span className="muted">
          Mittel aus {rating.sources.map((s) => RATING_SOURCE_LABEL[s]).join(", ")} · {rating.review_count.toLocaleString("de-DE")} Bewertungen
        </span>
      )}
    </span>
  );
}

const SOURCES: RatingSource[] = ["kununu", "glassdoor", "indeed", "google", "other"];

/** Bewertungen je Portal pflegen; neuer Wert = neuer Stand, Verlauf bleibt. */
export function RatingEditor({ company }: { company: Company }) {
  const toast = useToast();
  const add = useMutate((data: Parameters<typeof api.addCompanyRating>[1]) => api.addCompanyRating(company.id, data));
  const remove = useMutate((ratingId: number) => api.deleteCompanyRating(company.id, ratingId));
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ source: "kununu" as RatingSource, value: "", scale: "5", count: "", url: "" });
  const rating = company.employer_rating;
  const link = portalLink(form.source, company);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const value = Number(form.value.replace(",", "."));
    const scale = Number(form.scale.replace(",", ".")) || 5;
    if (!Number.isFinite(value) || value < 0 || value > scale) {
      toast(`Wert zwischen 0 und ${form.scale} angeben`, "error");
      return;
    }
    add.mutate(
      {
        source: form.source,
        value,
        scale_max: scale,
        review_count: form.count ? Number(form.count.replace(/\D/g, "")) : null,
        url: form.url.trim() || null,
      },
      {
        onSuccess: () => {
          toast("Bewertung gespeichert");
          setForm((f) => ({ ...f, value: "", count: "", url: "" }));
          setOpen(false);
        },
        onError: (err) => toast(err.message, "error"),
      },
    );
  };

  return (
    <div className="ratings">
      <div className="ratings__head">
        <h4>Arbeitgeber-Bewertung</h4>
        <button type="button" className="btn btn--ghost" onClick={() => setOpen((x) => !x)}>
          {open ? "Abbrechen" : "Bewertung eintragen"}
        </button>
      </div>
      {rating ? <RatingBadge rating={rating} /> : <p className="muted">Noch keine Bewertung erfasst.</p>}
      {rating && rating.current.length > 0 && (
        <ul className="ratings__list">
          {rating.current.map((c) => (
            <li key={c.id} className={rating.sources.includes(c.source) ? "" : "is-unused"}>
              <span className="ratings__src">{RATING_SOURCE_LABEL[c.source]}</span>
              <span>
                {num(c.raw_value, c.scale_max > 10 ? 0 : 1)}/{num(c.scale_max, 0)}
                {c.scale_max !== 5 && <span className="muted"> ({num(c.rating)})</span>}
              </span>
              <span className="muted">{c.review_count !== null ? `${c.review_count.toLocaleString("de-DE")} Bew.` : "Anzahl ?"}</span>
              <span className="muted">{formatDate(c.observed_at)}</span>
              {c.url ? (
                <a href={c.url} target="_blank" rel="noreferrer noopener" aria-label={`${RATING_SOURCE_LABEL[c.source]} öffnen`}>
                  ↗
                </a>
              ) : (
                <span />
              )}
              <button type="button" className="ratings__del" onClick={() => remove.mutate(c.id)} aria-label="Eintrag löschen" title="Fehleingabe löschen">
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && (
        <form className="ratings__form" onSubmit={submit}>
          <label>
            <span>Portal</span>
            <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value as RatingSource, scale: "5" })}>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {RATING_SOURCE_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Wert</span>
            <input inputMode="decimal" placeholder="3,8" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required />
          </label>
          <label>
            <span>von</span>
            <input inputMode="decimal" value={form.scale} onChange={(e) => setForm({ ...form, scale: e.target.value })} />
          </label>
          <label>
            <span>Anzahl Bewertungen</span>
            <input inputMode="numeric" placeholder="z. B. 420" value={form.count} onChange={(e) => setForm({ ...form, count: e.target.value })} />
          </label>
          <label className="ratings__url">
            <span>Link (optional)</span>
            <input inputMode="url" placeholder="kununu.com/de/…" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
          </label>
          <div className="ratings__actions">
            {link && (
              <a href={link} target="_blank" rel="noreferrer noopener">
                Auf {RATING_SOURCE_LABEL[form.source]} nachsehen ↗
              </a>
            )}
            <button type="submit" className="btn btn--primary" disabled={add.isPending}>
              Speichern
            </button>
          </div>
        </form>
      )}
      <p className="hint">
        Gesamtwert = arithmetisches Mittel der Portale mit mindestens {rating?.min_reviews ?? 10} Bewertungen, alle auf 5 Sterne umgerechnet. Neue Werte
        ersetzen den alten Stand, der Verlauf bleibt gespeichert.
      </p>
    </div>
  );
}
