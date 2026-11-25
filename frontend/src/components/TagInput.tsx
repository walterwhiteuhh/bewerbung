import { useId, useState, type KeyboardEvent } from "react";

import { useTags } from "../api/hooks";
import { addUnique, cleanTag, sameTag } from "../lib/tags";

interface Props {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

/** Hashtags als Chips; Enter, Leertaste oder Komma übernimmt, Backspace entfernt den letzten. */
export function TagInput({ value, onChange, placeholder = "#hashtag hinzufügen", autoFocus }: Props) {
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const { data: known } = useTags();
  const listId = useId();

  function commit(raw = draft): boolean {
    if (!raw.trim()) return true;
    const name = cleanTag(raw);
    if (!name) {
      setInvalid(true);
      return false;
    }
    // Bekannte Schreibweise übernehmen ("python" -> "Python"), damit keine Varianten entstehen.
    const canonical = known?.find((t) => sameTag(t.name, name))?.name ?? name;
    onChange(addUnique(value, canonical));
    setDraft("");
    setInvalid(false);
    return true;
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === "," || (e.key === " " && draft.trim())) {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  const suggestions = (known ?? []).filter((t) => !value.some((v) => sameTag(v, t.name)));

  return (
    <div className={`tag-input ${invalid ? "is-invalid" : ""}`}>
      {value.map((t) => (
        <span key={t} className="hashtag hashtag--removable">
          #{t}
          <button type="button" onClick={() => onChange(value.filter((x) => x !== t))} aria-label={`#${t} entfernen`}>
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={draft}
        list={listId}
        autoFocus={autoFocus}
        placeholder={value.length ? "" : placeholder}
        aria-label="Hashtag hinzufügen"
        aria-invalid={invalid}
        onChange={(e) => {
          setDraft(e.target.value);
          setInvalid(false);
        }}
        onKeyDown={onKeyDown}
        onBlur={() => commit()}
      />
      <datalist id={listId}>
        {suggestions.map((t) => (
          <option key={t.name} value={t.name} />
        ))}
      </datalist>
      {invalid && <span className="hint hint--warn tag-input__hint">Nur Buchstaben, Ziffern, - _ . (max. 40 Zeichen)</span>}
    </div>
  );
}

/** Hashtags anzeigen (Karten, Treffer); mit `onToggle` sind sie klickbar und filtern. */
export function TagList({ tags, active = [], onToggle }: { tags: string[]; active?: string[]; onToggle?: (tag: string) => void }) {
  if (tags.length === 0) return null;
  return (
    <p className="hashtags">
      {tags.map((t) => {
        const on = active.some((a) => sameTag(a, t));
        return onToggle ? (
          <button key={t} type="button" className={`hashtag hashtag--link ${on ? "is-active" : ""}`} aria-pressed={on} onClick={() => onToggle(t)}>
            #{t}
          </button>
        ) : (
          <span key={t} className={`hashtag ${on ? "is-active" : ""}`}>
            #{t}
          </span>
        );
      })}
    </p>
  );
}

/** Leiste mit allen Hashtags; ein Klick filtert (mehrere = alle müssen passen). */
export function TagFilterBar({ selected, onToggle }: { selected: string[]; onToggle: (tag: string) => void }) {
  const { data } = useTags();
  return <TagBar tags={data} selected={selected} onToggle={onToggle} />;
}

/** Wie `TagFilterBar`, aber mit eigener Liste (z. B. die Hashtags der Suchtreffer). */
export function TagBar({
  tags,
  selected,
  onToggle,
}: {
  tags: { name: string; count: number }[] | undefined;
  selected: string[];
  onToggle: (tag: string) => void;
}) {
  const data = tags;
  if (!data || data.length === 0) return null;
  return (
    <div className="tag-bar" role="toolbar" aria-label="Nach Hashtag filtern">
      {data.map((t) => {
        const on = selected.some((s) => sameTag(s, t.name));
        return (
          <button key={t.name} type="button" className={`hashtag hashtag--button ${on ? "is-active" : ""}`} aria-pressed={on} onClick={() => onToggle(t.name)}>
            #{t.name}
            <span className="hashtag__count">{t.count}</span>
          </button>
        );
      })}
    </div>
  );
}
