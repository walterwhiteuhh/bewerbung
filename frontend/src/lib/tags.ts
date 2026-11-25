/** Hashtags im Frontend: gleiche Regeln wie im Backend (domain/tags.py). */

const VALID = /^[\p{L}\p{N}_][\p{L}\p{N}_.-]*$/u;
const HASHTAG = /(?<![\p{L}\p{N}_#])#([\p{L}\p{N}_](?:[\p{L}\p{N}_.-]*[\p{L}\p{N}_])?)/gu;

/** "#Machine Learning " -> "Machine-Learning"; ungültig -> null. */
export function cleanTag(raw: string): string | null {
  const name = raw.trim().replace(/^#+/, "").trim().replace(/\s+/g, "-").replace(/^[-.]+|[-.]+$/g, "");
  return name && name.length <= 40 && VALID.test(name) ? name : null;
}

export const sameTag = (a: string, b: string) => a.localeCompare(b, "de", { sensitivity: "accent" }) === 0;

export function addUnique(list: string[], name: string): string[] {
  return list.some((t) => sameTag(t, name)) ? list : [...list, name];
}

/** Trennt "#python data #remote" in Freitext ("data") und Hashtags (["python", "remote"]). */
export function splitHashtags(input: string): { text: string; tags: string[] } {
  let tags: string[] = [];
  for (const m of input.matchAll(HASHTAG)) if (m[1]) tags = addUnique(tags, m[1]);
  const text = input.replace(HASHTAG, " ").replace(/\s+/g, " ").trim();
  return { text, tags };
}
