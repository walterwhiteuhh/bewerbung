import type { PostingListItem } from "../api/types";
import { formatSalary, relativeTime } from "../lib/format";
import { REMOTE_LABEL } from "../lib/labels";
import { MetaLine, Priority, SourceTag, StatusPill } from "./Badges";
import { TagList } from "./TagInput";

interface Props {
  items: PostingListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  loading: boolean;
  onCreate: () => void;
  filtered: boolean;
  activeTags?: string[];
}

export function PostingList({ items, selectedId, onSelect, loading, onCreate, filtered, activeTags = [] }: Props) {
  if (loading && items.length === 0) {
    return (
      <ul className="list" aria-busy>
        {[0, 1, 2].map((i) => (
          <li key={i} className="card card--skeleton" />
        ))}
      </ul>
    );
  }
  if (items.length === 0) {
    return (
      <div className="empty">
        <p className="empty__title">{filtered ? "Keine Treffer" : "Noch keine Stellen erfasst"}</p>
        <p>{filtered ? "Passe Suche oder Filter an." : "Füge eine LinkedIn- oder Stepstone-URL ein und leg los."}</p>
        {!filtered && (
          <button type="button" className="btn btn--primary" onClick={onCreate}>
            Erste Stelle erfassen
          </button>
        )}
      </div>
    );
  }

  return (
    <ul className="list">
      {items.map((p) => {
        const salary = formatSalary(p.salary_min, p.salary_max, p.salary_currency);
        return (
          <li key={p.id}>
            <button
              type="button"
              className={`card ${p.application ? `status-${p.application.current_status}` : ""} ${p.id === selectedId ? "is-selected" : ""}`}
              onClick={() => onSelect(p.id)}
              aria-current={p.id === selectedId}
            >
              <div className="card__top">
                {p.application && <StatusPill status={p.application.current_status} />}
                <SourceTag source={p.source} />
              </div>
              <h3 className="card__title">{p.title}</h3>
              <p className="card__company">{p.company?.name ?? "Firma unbekannt"}</p>
              <MetaLine items={[p.location, p.remote_type !== "unknown" ? REMOTE_LABEL[p.remote_type] : null, salary]} />
              <TagList tags={p.tags} active={activeTags} />
              <div className="card__bottom">
                <span className="muted">{relativeTime(p.updated_at)}</span>
                {p.application && <Priority value={p.application.priority} />}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
