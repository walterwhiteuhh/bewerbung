import { useCallback, useEffect, useState } from "react";

export type View = "home" | "list" | "search";

let openedInApp = false; // nur dann darf "Schließen" per history.back() zurückspringen

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

/** Ansicht aus dem Hash: leer oder #/start = Startseite, #/suche = Suche, sonst die eigene Liste. */
export function useView(): [View, (v: View) => void] {
  const hash = useHash();
  const view: View = hash.startsWith("#/suche")
    ? "search"
    : hash === "" || hash === "#" || hash.startsWith("#/start")
      ? "home"
      : "list";
  const setView = useCallback((v: View) => {
    window.location.hash = v === "search" ? "/suche" : "/";
  }, []);
  return [view, setView];
}

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
      if (openedInApp) {
        openedInApp = false;
        history.back();
      } else {
        window.location.hash = "/";
      }
      return;
    }
    openedInApp = true;
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
