import { usePostingInsights } from "../api/hooks";
import type { JobFeatures, JobSource, ListingBrief, SimilarJob } from "../api/types";
import { relativeTime } from "../lib/format";
import { SOURCE_LABEL, STATUS_LABEL } from "../lib/labels";
import { SourceTag } from "./Badges";

const pct = (x: number) => `${Math.round(x * 100)} %`;

export function distanceLabel(f: JobFeatures): string | null {
  if (f.distance_km === null) return null;
  const km = f.distance_km < 10 ? f.distance_km.toFixed(1).replace(".", ",") : Math.round(f.distance_km).toString();
  return `${f.distance_estimated ? "ca. " : ""}${km} km`;
}

function ageLabel(days: number | null): string | null {
  if (days === null) return null;
  if (days === 0) return "seit heute online";
  if (days === 1) return "seit gestern online";
  return `seit ${days} Tagen online`;
}

/** Kompakte Merkmale einer Anzeige, für Trefferkarten und die Detailansicht. */
export function FeatureChips({ features: f, hideCompany = false }: { features: JobFeatures; hideCompany?: boolean }) {
  const chips: { text: string; tone?: "good" | "warn" | "info"; title?: string }[] = [];
  const dist = distanceLabel(f);
  if (dist) chips.push({ text: dist, tone: f.within_max_distance === false ? "warn" : f.within_max_distance ? "good" : undefined, title: f.distance_estimated ? "Ort ohne genaue Koordinaten, Stadtmitte geschätzt" : "Luftlinie zu deinem Wohnort" });
  if (f.match_score !== null)
    chips.push({
      text: `Passt ${pct(f.match_score)}`,
      tone: f.match_score >= 0.6 ? "good" : f.match_score < 0.3 ? "warn" : undefined,
      title: [f.matched_skills.length && `Hast du: ${f.matched_skills.join(", ")}`, f.missing_skills.length && `Fehlt: ${f.missing_skills.join(", ")}`].filter(Boolean).join("\n"),
    });
  const age = ageLabel(f.age_days);
  if (age) chips.push({ text: age, tone: f.age_days !== null && f.age_days > 30 ? "warn" : undefined });
  if (f.portals.length > 1) chips.push({ text: `auf ${f.portals.length} Portalen`, title: f.portals.map((p) => SOURCE_LABEL[p]).join(", "), tone: "info" });
  if (f.is_repost) chips.push({ text: "neu ausgeschrieben", tone: "info", title: "Dieselbe Stelle wurde erneut veröffentlicht" });
  const c = f.company;
  if (c && !hideCompany) {
    if (c.applications > 0) chips.push({ text: c.rejections ? `Firma: ${c.rejections}× Absage` : `Firma: ${c.applications}× beworben`, tone: c.rejections ? "warn" : "info" });
    else if (c.saved_postings > 0) chips.push({ text: `Firma: ${c.saved_postings}× gemerkt`, tone: "info" });
    if (c.listings > 1) chips.push({ text: `${c.listings} Anzeigen der Firma`, title: `${c.active_listings} davon in den letzten 14 Tagen gesehen` });
  }
  if (f.similar_saved) chips.push({ text: `ähnlich: ${f.similar_saved.title}`, title: `Ähnlichkeit ${pct(f.similar_saved.score)} · ${f.similar_saved.shared.join(", ")}` });
  if (!chips.length) return null;
  return (
    <ul className="feats" aria-label="Merkmale">
      {chips.map((ch) => (
        <li key={ch.text} className={`feat ${ch.tone ? `feat--${ch.tone}` : ""}`} title={ch.title}>
          {ch.text}
        </li>
      ))}
    </ul>
  );
}

function BriefRow({ b }: { b: ListingBrief }) {
  const body = (
    <>
      <SourceTag source={b.source as JobSource} />
      <span className="rel__title">{b.title}</span>
      <span className="muted">{[b.city, `zuletzt ${relativeTime(b.last_seen_at)}`].filter(Boolean).join(" · ")}</span>
    </>
  );
  return <li className="rel__row">{b.url ? <a href={b.url} target="_blank" rel="noreferrer noopener">{body}</a> : <div>{body}</div>}</li>;
}

function SimilarRow({ s }: { s: SimilarJob }) {
  const status = s.kind === "posting" && s.score === 1 && s.shared[0] ? STATUS_LABEL[s.shared[0] as keyof typeof STATUS_LABEL] : null;
  const body = (
    <>
      <span className="rel__score">{status ?? pct(s.score)}</span>
      <span className="rel__title">{s.title}</span>
      <span className="muted">{[s.company_name, !status && s.shared.slice(0, 4).join(", ")].filter(Boolean).join(" · ")}</span>
    </>
  );
  return <li className="rel__row">{s.kind === "posting" ? <a href={`#/stelle/${s.id}`}>{body}</a> : <div>{body}</div>}</li>;
}

/** Querbezüge einer gemerkten Stelle: andere Portale, gleiche Firma, ähnliche Stellen. */
export function InsightsSection({ postingId }: { postingId: number }) {
  const { data } = usePostingInsights(postingId);
  if (!data) return null;
  const { features, other_portals, same_company_postings, same_company_listings, similar } = data;
  const empty = !other_portals.length && !same_company_postings.length && !same_company_listings.length && !similar.length;
  return (
    <section className="section rel">
      <h3>Zusammenhänge</h3>
      <FeatureChips features={features} />
      {other_portals.length > 0 && (
        <div className="rel__group">
          <h4>Dieselbe Stelle auf anderen Portalen</h4>
          <ul>{other_portals.map((b) => <BriefRow key={b.id} b={b} />)}</ul>
        </div>
      )}
      {(same_company_postings.length > 0 || same_company_listings.length > 0) && (
        <div className="rel__group">
          <h4>Weitere Stellen dieser Firma</h4>
          <ul>
            {same_company_postings.map((s) => <SimilarRow key={`p${s.id}`} s={s} />)}
            {same_company_listings.map((b) => <BriefRow key={`l${b.id}`} b={b} />)}
          </ul>
        </div>
      )}
      {similar.length > 0 && (
        <div className="rel__group">
          <h4>Ähnliche Stellen</h4>
          <ul>{similar.map((s) => <SimilarRow key={`${s.kind}${s.id}`} s={s} />)}</ul>
        </div>
      )}
      {empty && <p className="hint">Noch keine Querbezüge. Sie entstehen mit jeder Suche in den Portalen.</p>}
    </section>
  );
}
