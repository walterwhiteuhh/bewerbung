import { useCallback, useEffect, useState } from "react";

/** Minimales Routing über den Hash (#/stelle/12). Zurück-Taste schließt so das Detail auf dem Handy. */
export function useSelectedId(): [number | null, (id: number | null) => void] {
  const parse = () => {
    const m = /^#\/stelle\/(\d+)$/.exec(window.location.hash);
    return m ? Number(m[1]) : null;
  };
  const [id, setId] = useState<number | null>(parse);

  useEffect(() => {
    const onChange = () => setId(parse());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const select = useCallback((next: number | null) => {
    if (next === null) {
      if (window.location.hash) history.back();
      return;
    }
    window.location.hash = `/stelle/${next}`;
  }, []);

  return [id, select];
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
