import type { ReactNode } from "react";
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

/** Metadaten als einzelne Elemente; Trenner kommen aus dem CSS. */
export function MetaLine({
  items,
  lead,
  className = "card__meta",
}: {
  items: (string | null | undefined)[];
  lead?: ReactNode;
  className?: string;
}) {
  const shown = items.filter((m): m is string => Boolean(m));
  if (shown.length === 0 && !lead) return null;
  return (
    <p className={className}>
      {lead && <span>{lead}</span>}
      {shown.map((m) => (
        <span key={m}>{m}</span>
      ))}
    </p>
  );
}
