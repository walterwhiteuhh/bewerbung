import { REMOTE_TYPES, type PostingFilter, type RemoteType } from "../api/types";
import { REMOTE_LABEL } from "../lib/labels";

type Extra = Pick<PostingFilter, "remote" | "location" | "minSalary" | "followUpDue" | "includeArchived">;

interface Props {
  value: Extra;
  onChange: (v: Extra) => void;
}

export const EMPTY_EXTRA: Extra = { remote: [], location: "", minSalary: null, followUpDue: false, includeArchived: false };

export const activeFilterCount = (v: Extra) =>
  v.remote.length + (v.location ? 1 : 0) + (v.minSalary !== null ? 1 : 0) + (v.followUpDue ? 1 : 0) + (v.includeArchived ? 1 : 0);

/** Erweiterte Filter für die eigenen Stellen. */
export function FilterPanel({ value, onChange }: Props) {
  const set = <K extends keyof Extra>(k: K, v: Extra[K]) => onChange({ ...value, [k]: v });
  const toggleRemote = (r: RemoteType) =>
    set("remote", value.remote.includes(r) ? value.remote.filter((x) => x !== r) : [...value.remote, r]);

  return (
    <div className="filter-panel">
      <div className="filter-panel__row">
        {REMOTE_TYPES.filter((r) => r !== "unknown").map((r) => (
          <button key={r} type="button" className={`chip ${value.remote.includes(r) ? "is-active" : ""}`} onClick={() => toggleRemote(r)}>
            {REMOTE_LABEL[r]}
          </button>
        ))}
      </div>
      <div className="filter-panel__grid">
        <label className="field">
          <span>Ort enthält</span>
          <input value={value.location} placeholder="z. B. Hamburg" onChange={(e) => set("location", e.target.value)} />
        </label>
        <label className="field">
          <span>Gehalt ab (€/Jahr)</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            step={5000}
            value={value.minSalary ?? ""}
            onChange={(e) => set("minSalary", e.target.value === "" ? null : Number(e.target.value))}
          />
        </label>
      </div>
      <div className="filter-panel__row">
        <label className="toggle">
          <input type="checkbox" checked={value.followUpDue} onChange={(e) => set("followUpDue", e.target.checked)} />
          Nachfassen fällig
        </label>
        <label className="toggle">
          <input type="checkbox" checked={value.includeArchived} onChange={(e) => set("includeArchived", e.target.checked)} />
          Archivierte zeigen
        </label>
        {activeFilterCount(value) > 0 && (
          <button type="button" className="link" onClick={() => onChange(EMPTY_EXTRA)}>
            Zurücksetzen
          </button>
        )}
      </div>
    </div>
  );
}
