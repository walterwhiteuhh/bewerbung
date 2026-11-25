/**
 * Ein Hashtag über alle Objekte: Stellen, Firmen, Unterlagen, gespeicherte Suchen.
 * Dazu die im Hintergrund eingeschlossenen Begriffe (Unterbegriffe, Synonyme) und verwandte Tags.
 */
import { useTagOverview } from "../api/hooks";
import type { LinkedItem } from "../api/types";
import { Dialog } from "./Dialog";

interface Props {
  tag: string | null;
  onClose: () => void;
  onPickTag: (tag: string) => void;
}

function Group({ title, items, href }: { title: string; items: LinkedItem[]; href?: (i: LinkedItem) => string | undefined }) {
  if (items.length === 0) return null;
  return (
    <section className="tagov__group">
      <h4>
        {title} <span className="muted">{items.length}</span>
      </h4>
      <ul>
        {items.slice(0, 12).map((i) => {
          const link = href?.(i);
          return <li key={i.id}>{link ? <a href={link}>{i.label}</a> : i.label}</li>;
        })}
        {items.length > 12 && <li className="muted">… und {items.length - 12} weitere</li>}
      </ul>
    </section>
  );
}

export function TagOverviewDialog({ tag, onClose, onPickTag }: Props) {
  const { data, isLoading, isError } = useTagOverview(tag);
  const extra = (data?.includes ?? []).filter((t) => t.toLocaleLowerCase("de") !== data?.tag.toLocaleLowerCase("de"));
  const empty = data && !data.postings.length && !data.company.length && !data.document.length && !data.search_profile.length;

  return (
    <Dialog open={tag !== null} title={tag ? `#${tag}` : "Hashtag"} onClose={onClose}>
      {isLoading && <p className="muted">Lade …</p>}
      {isError && <p className="muted">Zu diesem Hashtag gibt es noch nichts.</p>}
      {data && (
        <div className="tagov">
          {extra.length > 0 && (
            <p className="muted tagov__includes">
              Schließt mit ein: {extra.map((t) => `#${t}`).join(", ")}
            </p>
          )}
          {empty && <p className="muted">Noch nichts mit diesem Hashtag verknüpft.</p>}
          <Group
            title="Stellen"
            items={data.postings}
            href={(i) => `#/stelle/${i.id}`}
          />
          <Group title="Firmen" items={data.company} />
          <Group title="Unterlagen" items={data.document} />
          <Group title="Gespeicherte Suchen" items={data.search_profile} />
          {data.related.length > 0 && (
            <section className="tagov__group">
              <h4>Verwandt</h4>
              <p className="hashtags">
                {data.related.map((t) => (
                  <button key={t} type="button" className="hashtag hashtag--link" onClick={() => onPickTag(t)}>
                    #{t}
                  </button>
                ))}
              </p>
            </section>
          )}
        </div>
      )}
    </Dialog>
  );
}
