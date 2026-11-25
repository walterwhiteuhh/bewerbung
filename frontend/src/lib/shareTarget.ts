/** Teilen-Ziel der installierten App: „Teilen → Anheuern“ öffnet `/?title=…&text=…&url=…`. */

const URL_RE = /https?:\/\/[^\s<>"']+/i;

/** Holt die Anzeigen-URL aus den Teilen-Parametern. LinkedIn & Co. packen sie oft in `text`. */
export function extractSharedUrl(search: string): string | null {
  const params = new URLSearchParams(search);
  for (const key of ["url", "text", "title"]) {
    const m = URL_RE.exec(params.get(key) ?? "");
    if (m) return m[0].replace(/[).,;]+$/, "");
  }
  return null;
}

let pending: string | null = null;

/** Beim Start einmal aufrufen: merkt sich die geteilte URL und räumt die Adresszeile auf. */
export function captureSharedUrl(): void {
  if (typeof window === "undefined") return;
  const url = extractSharedUrl(window.location.search);
  if (url) {
    pending = url;
    window.history.replaceState(null, "", "/#/");
  }
}

export const peekSharedUrl = (): string | null => pending;
export const clearSharedUrl = (): void => {
  pending = null;
};
