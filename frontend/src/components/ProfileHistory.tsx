import { usePrimaryCvHistory, useProfileHistory } from "../api/hooks";
import { formatDateTime } from "../lib/format";
import { describePeriod, describeSkills, describeVersion, usageText } from "../lib/history";

/** Was sich im Profil und beim Haupt-Lebenslauf wann geändert hat, und womit Bewerbungen rausgingen. */
export function ProfileHistory() {
  const versions = useProfileHistory();
  const periods = usePrimaryCvHistory();

  return (
    <div className="history">
      <p className="hint">
        Jede Änderung am Profil bleibt als Stand erhalten. Bei jeder Bewerbung wird festgehalten, mit welchem Stand und
        welchem Haupt-Lebenslauf sie rausging.
      </p>

      <section className="section" aria-labelledby="hist-profile">
        <h3 id="hist-profile">Profilstände</h3>
        {versions.isLoading ? (
          <p className="muted">Lade …</p>
        ) : !versions.data?.length ? (
          <p className="muted">Noch kein Stand gespeichert. Speichere dein Profil unter „Angaben“.</p>
        ) : (
          <ol className="timeline">
            {versions.data.map((v, i) => (
              <li key={v.id} className="timeline__item timeline__item--event">
                <span className="timeline__dot" aria-hidden />
                <div>
                  <p className="timeline__event">
                    {describeVersion(v)}
                    {i === 0 && <span className="badge-primary">aktuell</span>}
                  </p>
                  {describeSkills(v) && <p className="timeline__detail">{describeSkills(v)}</p>}
                  <time dateTime={v.created_at} className="muted">
                    {formatDateTime(v.created_at)} · {usageText(v.application_count)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="section" aria-labelledby="hist-cv">
        <h3 id="hist-cv">Haupt-Lebenslauf</h3>
        {periods.isLoading ? (
          <p className="muted">Lade …</p>
        ) : !periods.data?.length ? (
          <p className="muted">Noch kein Lebenslauf als Haupt-Lebenslauf festgelegt (siehe „Unterlagen“).</p>
        ) : (
          <ol className="timeline">
            {periods.data.map((p) => (
              <li key={`${p.document_id}-${p.started_at}`} className="timeline__item timeline__item--event">
                <span className="timeline__dot" aria-hidden />
                <div>
                  <p className="timeline__event">
                    {p.title}
                    {p.archived && <span className="muted"> (archiviert)</span>}
                    {!p.ended_at && <span className="badge-primary">aktuell</span>}
                  </p>
                  <time className="muted">
                    {describePeriod(p)} · {usageText(p.application_count)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
