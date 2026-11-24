import { useStats } from "../api/hooks";
import { STATUSES, type ApplicationStatus } from "../api/types";
import { STATUS_LABEL } from "../lib/labels";

interface Props {
  selected: ApplicationStatus[];
  onToggle: (s: ApplicationStatus | null) => void;
}

/** Status-Chips mit Zählern; dienen gleichzeitig als Filter. Auf dem Handy horizontal scrollbar. */
export function StatsBar({ selected, onToggle }: Props) {
  const { data } = useStats();
  const count = (s: string) => data?.by_status.find((b) => b.key === s)?.count ?? 0;

  return (
    <div className="stats">
      <div className="stats__kpis">
        <div>
          <strong>{data?.active ?? "–"}</strong>
          <span>aktiv</span>
        </div>
        <div>
          <strong>{data?.total ?? "–"}</strong>
          <span>gesamt</span>
        </div>
        <div>
          <strong>{data?.response_rate != null ? `${Math.round(data.response_rate * 100)} %` : "–"}</strong>
          <span>Rücklauf</span>
        </div>
      </div>
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
    </div>
  );
}
