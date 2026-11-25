import { api } from "../api/client";
import { useMutate } from "../api/hooks";
import type { Company, CompanyUpdate } from "../api/types";
import { CompanyLogo } from "./CompanyLogo";
import { EntityTags } from "./EntityTags";
import { SocialLinks } from "./SocialLinks";
import { RatingEditor } from "./EmployerRating";
import { useToast } from "./Toast";

const LOGO_SOURCE_LABEL: Record<string, string> = {
  portal: "Logo aus der Anzeige",
  website: "Logo von der Website",
  manual: "Logo selbst gesetzt",
};

function host(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Stammdaten der Firma direkt in der Stelle pflegen; Änderungen gelten für alle Stellen der Firma. */
export function CompanySection({ company }: { company: Company }) {
  const toast = useToast();
  const update = useMutate((data: CompanyUpdate) => api.updateCompany(company.id, data));
  const fetchLogo = useMutate(() => api.fetchCompanyLogo(company.id));

  const loadLogo = (quiet = false) =>
    fetchLogo.mutate(undefined, {
      onSuccess: (c) => toast(c.logo_source === "website" ? "Logo und Profile von der Website übernommen" : "Profile von der Website übernommen"),
      onError: (e) => toast(quiet ? `Website gespeichert, aber ${e.message.replace(/^Logo/, "kein Logo")}` : e.message, "error"),
    });

  const save = (data: CompanyUpdate) =>
    update.mutate(data, {
      onSuccess: (c) => {
        // Neue Website und noch kein Logo: gleich versuchen, eins zu holen.
        if (data.website && !c.logo_url) loadLogo(true);
      },
      onError: (e) => toast(e.message, "error"),
    });

  const socialText = Object.values(company.social_links ?? {}).join(" ");

  const blurSave = (field: keyof CompanyUpdate, current: string | null) => (e: React.FocusEvent<HTMLInputElement>) => {
    const value = e.target.value.trim();
    if (value !== (current ?? "")) save({ [field]: value || null });
  };

  return (
    <section className="section company">
      <div className="company__head">
        <CompanyLogo name={company.name} url={company.logo_url} size="md" />
        <div className="company__title">
          <h3>{company.name}</h3>
          <p className="muted">
            {company.website ? (
              <a href={company.website} target="_blank" rel="noreferrer noopener">
                {host(company.website)} ↗
              </a>
            ) : (
              "Keine Website hinterlegt"
            )}
            {company.logo_source && ` · ${LOGO_SOURCE_LABEL[company.logo_source] ?? ""}`}
          </p>
        </div>
        <div className="company__actions">
          {company.website && (
            <button type="button" className="btn" onClick={() => loadLogo()} disabled={fetchLogo.isPending}>
              {fetchLogo.isPending ? "Lade …" : company.logo_url ? "Von Website neu laden" : "Logo & Profile laden"}
            </button>
          )}
          {company.logo_url && (
            <button type="button" className="btn btn--ghost" onClick={() => save({ logo_url: null })}>
              Logo entfernen
            </button>
          )}
        </div>
      </div>
      <SocialLinks links={company.social_links} />
      <div className="company__tags">
        <span className="muted">Hashtags der Firma</span>
        <EntityTags type="company" id={company.id} placeholder="#wunscharbeitgeber hinzufügen" />
      </div>
      <div className="facts facts--edit">
        <label className="fact">
          <span>Website</span>
          <input
            key={`w${company.website}`}
            defaultValue={company.website ?? ""}
            placeholder="firma.de"
            inputMode="url"
            onBlur={blurSave("website", company.website)}
          />
        </label>
        <label className="fact">
          <span>Branche</span>
          <input key={`i${company.industry}`} defaultValue={company.industry ?? ""} placeholder="z. B. Logistik" onBlur={blurSave("industry", company.industry)} />
        </label>
        <label className="fact">
          <span>Firmensitz</span>
          <input key={`l${company.location}`} defaultValue={company.location ?? ""} placeholder="Ort" onBlur={blurSave("location", company.location)} />
        </label>
      </div>
      <div className="facts facts--edit facts--one">
        <label className="fact">
          <span>Social Media</span>
          <input
            key={`s${socialText}`}
            defaultValue={socialText}
            placeholder="linkedin.com/company/… xing.com/pages/…"
            onBlur={(e) => {
              const value = e.target.value.trim();
              if (value !== socialText) save({ social_links: value ? value.split(/[\s,]+/) : [] });
            }}
          />
        </label>
      </div>
      <RatingEditor company={company} />
      <p className="hint">Gilt für alle Stellen dieser Firma. Profile werden auch aus der Anzeige und von der Website übernommen.</p>
    </section>
  );
}
