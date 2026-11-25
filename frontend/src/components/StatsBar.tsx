import { useStats } from "../api/hooks";
import { STATUSES, type ApplicationStatus } from "../api/types";
import { STATUS_LABEL } from "../lib/labels";

interface Props {
  selected: ApplicationStatus[];
  onToggle: (s: ApplicationStatus | null) => void;
}

/**
 * Kopfbereich "Pipeline": Kennzahlen, ein Balken mit der Verteilung über alle Status
 * und Status-Chips, die gleichzeitig als Filter dienen.
 */
export function StatsBar({ selected, onToggle }: Props) {
  const { data } = useStats();
  const count = (s: string) => data?.by_status.find((b) => b.key === s)?.count ?? 0;
  const filled = STATUSES.filter((s) => count(s) > 0);
  const rate = data?.response_rate != null ? `${Math.round(data.response_rate * 100)} %` : "–";

  return (
    <section className="pipeline" aria-label="Überblick">
      <div className="pipeline__kpis">
        <p className="kpi kpi--lead">
          <strong>{data?.active ?? "–"}</strong>
          <span>laufende Bewerbungen</span>
        </p>
        <p className="kpi">
          <strong>{data?.total ?? "–"}</strong>
          <span>Stellen erfasst</span>
        </p>
        <p className="kpi">
          <strong>{rate}</strong>
          <span>Rücklaufquote</span>
        </p>
      </div>

      {filled.length > 0 && (
        <div className="pipeline__bar" aria-hidden>
          {filled.map((s) => (
            <span
              key={s}
              className={`pipeline__seg status-${s} ${selected.length && !selected.includes(s) ? "is-dim" : ""}`}
              style={{ flexGrow: count(s) }}
              title={`${STATUS_LABEL[s]}: ${count(s)}`}
            />
          ))}
        </div>
      )}

      <div className="chips" role="toolbar" aria-label="Nach Status filtern">
        <button type="button" className={`chip ${selected.length === 0 ? "is-active" : ""}`} onClick={() => onToggle(null)}>
          Alle
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            className={`chip status-${s} ${selected.includes(s) ? "is-active" : ""}`}
            aria-pressed={selected.includes(s)}
            onClick={() => onToggle(s)}
          >
            <span className="dot" aria-hidden />
            {STATUS_LABEL[s]}
            <span className="chip__count">{count(s)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
