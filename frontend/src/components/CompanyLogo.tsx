import { useState } from "react";

/** Kleines Firmenlogo; ohne Logo (oder wenn es nicht lädt) ein Monogramm aus den Initialen. */
export function CompanyLogo({ name, url, size = "sm" }: { name: string | null | undefined; url: string | null | undefined; size?: "sm" | "md" }) {
  const [failed, setFailed] = useState<string | null>(null);
  const label = (name ?? "").trim();
  if (url && failed !== url) {
    return (
      <span className={`logo logo--${size}`}>
        <img src={url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(url)} />
      </span>
    );
  }
  if (!label) return null;
  return (
    <span className={`logo logo--${size} logo--mono`} aria-hidden>
      {initials(label)}
    </span>
  );
}

function initials(name: string): string {
  const words = name
    .replace(/\b(gmbh|ag|se|kg|mbh|co|inc|ltd|llc|e\.?\s?v\.?|ug)\b\.?/gi, "")
    .split(/[\s&+\-/.,]+/)
    .filter((w) => /[\p{L}\p{N}]/u.test(w));
  const letters: string[] = words.length > 1 ? words.slice(0, 2) : [words[0] ?? name];
  return letters
    .map((w) => Array.from(w)[0] ?? "")
    .join("")
    .toUpperCase();
}
