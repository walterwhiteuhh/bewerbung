import type { ApplicationStatus, JobSource } from "../api/types";
import { SOURCE_LABEL, STATUS_LABEL } from "../lib/labels";

export function StatusPill({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`pill status-${status}`}>
      <span className="dot" aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function SourceTag({ source }: { source: JobSource }) {
  return <span className={`tag source-${source}`}>{SOURCE_LABEL[source]}</span>;
}

export function Priority({ value, onChange }: { value: number; onChange?: (v: number) => void }) {
  return (
    <span className="priority" aria-label={`Priorität ${value} von 5`}>
      {[1, 2, 3, 4, 5].map((n) =>
        onChange ? (
          <button
            key={n}
            type="button"
            className={n <= value ? "on" : ""}
            onClick={() => onChange(n)}
            aria-label={`Priorität ${n}`}
          >
            ●
          </button>
        ) : (
          <span key={n} className={n <= value ? "on" : ""} aria-hidden>
            ●
          </span>
        ),
      )}
    </span>
  );
}
