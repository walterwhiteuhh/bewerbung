import type { SocialLinks as Links, SocialNetwork } from "../api/types";

export const SOCIAL_LABEL: Record<SocialNetwork, string> = {
  linkedin: "LinkedIn",
  xing: "XING",
  kununu: "kununu",
  instagram: "Instagram",
  facebook: "Facebook",
  youtube: "YouTube",
  x: "X",
  tiktok: "TikTok",
  github: "GitHub",
};

const ORDER = Object.keys(SOCIAL_LABEL) as SocialNetwork[];

/** Profile der Firma als kleine Link-Chips (nur, was bekannt ist). */
export function SocialLinks({ links, website }: { links: Links | null | undefined; website?: string | null }) {
  const shown = ORDER.filter((n) => links?.[n]);
  if (!shown.length && !website) return null;
  return (
    <ul className="socials" aria-label="Firma im Netz">
      {website && (
        <li>
          <a className="social social--web" href={website} target="_blank" rel="noreferrer noopener">
            Website
          </a>
        </li>
      )}
      {shown.map((n) => (
        <li key={n}>
          <a className={`social social--${n}`} href={links![n]} target="_blank" rel="noreferrer noopener" title={links![n]}>
            {SOCIAL_LABEL[n]}
          </a>
        </li>
      ))}
    </ul>
  );
}
