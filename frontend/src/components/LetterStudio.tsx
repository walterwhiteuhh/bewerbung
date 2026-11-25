import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useGenerators, useLetterContext, useLetters, useMutate } from "../api/hooks";
import type { CoverLetter, GeneratorName, LetterLength, LetterRequest, LetterTone, PostingDetail } from "../api/types";
import { formatDateTime } from "../lib/format";
import { TagList } from "./TagInput";
import { useToast } from "./Toast";

const TONES: { value: LetterTone; label: string }[] = [
  { value: "formell", label: "Formell" },
  { value: "modern", label: "Modern" },
  { value: "locker", label: "Locker" },
];
const LENGTHS: { value: LetterLength; label: string }[] = [
  { value: "kurz", label: "Kurz" },
  { value: "normal", label: "Normal" },
  { value: "ausfuehrlich", label: "Ausführlich" },
];
export const GENERATOR_LABEL: Record<GeneratorName, string> = {
  claude: "Claude",
  openai: "ChatGPT",
  gemini: "Gemini",
  template: "Vorlage",
};

interface Props {
  posting: PostingDetail;
  onOpenProfile: () => void;
}

/**
 * Anschreiben-Werkstatt: zeigt, was automatisch erkannt wurde (Portal, Hashtags, passende Skills),
 * erzeugt neue Fassungen und lässt jede Fassung bearbeiten. Ältere Fassungen bleiben erhalten.
 */
export function LetterStudio({ posting, onOpenProfile }: Props) {
  const toast = useToast();
  const { data: ctx } = useLetterContext(posting.id);
  const { data: generators = [] } = useGenerators();
  const { data: letters = [] } = useLetters(posting.id);
  const [req, setReq] = useState<LetterRequest>({ generator: "auto", tone: "modern", length: "normal", extra_notes: null });
  const [activeId, setActiveId] = useState<number | null>(null);
  const generate = useMutate((r: LetterRequest) => api.generateLetter(posting.id, r));

  const active = letters.find((l) => l.id === activeId) ?? letters[0] ?? null;
  const autoPick = generators.find((g) => g.available);
  const aiAvailable = generators.some((g) => g.available && g.name !== "template");

  function run() {
    generate.mutate(req, {
      onSuccess: (letter) => {
        setActiveId(letter.id);
        toast(`Fassung ${letter.version} erstellt`);
        // Auf dem Handy liegt der Text unter den Einstellungen: dorthin springen.
        setTimeout(() => document.querySelector(".studio__main")?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
      },
      onError: (e) => toast(e.message, "error"),
    });
  }

  return (
    <div className="studio">
      <aside className="studio__side">
        <section className="studio__box">
          <h3>Automatisch erkannt</h3>
          <dl className="studio__facts">
            <dt>Portal</dt>
            <dd>{ctx?.portal ?? "manuell erfasst"}</dd>
            <dt>Firma</dt>
            <dd>{posting.company?.name ?? "–"}</dd>
          </dl>
          {ctx && (ctx.tags.length > 0 ? <TagList tags={ctx.tags} /> : ctx.suggested_tags.length > 0 && (
            <>
              <p className="hint">Vorgeschlagen aus der Beschreibung:</p>
              <TagList tags={ctx.suggested_tags} />
            </>
          ))}
          {ctx && ctx.matching_skills.length > 0 && (
            <p className="studio__skills">
              <span className="hint">Passt zu deinem Profil:</span> {ctx.matching_skills.join(", ")}
            </p>
          )}
          {ctx?.description_excerpt ? (
            <details className="studio__excerpt">
              <summary>Beschreibung ({ctx.description_excerpt.length > 400 ? "Auszug" : "vollständig"})</summary>
              <p className="prose">{ctx.description_excerpt}</p>
            </details>
          ) : (
            <p className="hint hint--warn">Keine Beschreibung hinterlegt. Das Anschreiben wird dadurch allgemeiner.</p>
          )}
        </section>

        {ctx && !ctx.profile_complete && (
          <section className="studio__box studio__box--warn">
            <p>
              Dein Profil ist noch unvollständig: <strong>{ctx.missing_profile_fields.join(", ")}</strong>. Ohne diese Angaben
              bleibt der Text allgemein.
            </p>
            <button type="button" className="btn btn--small" onClick={onOpenProfile}>
              Profil ergänzen
            </button>
          </section>
        )}

        <section className="studio__box">
          <h3>Einstellungen</h3>
          <label className="field">
            <span>Erstellt mit</span>
            <select value={req.generator} onChange={(e) => setReq({ ...req, generator: e.target.value as LetterRequest["generator"] })}>
              <option value="auto">Automatisch{autoPick ? ` (${GENERATOR_LABEL[autoPick.name]})` : ""}</option>
              {generators.map((g) => (
                <option key={g.name} value={g.name} disabled={!g.available}>
                  {GENERATOR_LABEL[g.name] ?? g.label}
                  {g.model ? ` · ${g.model}` : ""}
                  {g.available ? "" : " (kein Key)"}
                </option>
              ))}
            </select>
          </label>
          {!aiAvailable && generators.length > 0 && (
            <p className="hint">Ohne API-Key entsteht ein Entwurf aus einer Vorlage. Keys für Claude, ChatGPT oder Gemini kommen in die .env.</p>
          )}
          <Choice label="Ton" options={TONES} value={req.tone} onChange={(tone) => setReq({ ...req, tone })} />
          <Choice label="Länge" options={LENGTHS} value={req.length} onChange={(length) => setReq({ ...req, length })} />
          <label className="field">
            <span>Hinweise (optional)</span>
            <textarea
              rows={3}
              placeholder="z. B. Projekt X hervorheben, Umzug nach Hamburg erwähnen"
              value={req.extra_notes ?? ""}
              onChange={(e) => setReq({ ...req, extra_notes: e.target.value || null })}
            />
          </label>
          <button type="button" className="btn btn--primary studio__go" onClick={run} disabled={generate.isPending}>
            {generate.isPending ? "Schreibe …" : letters.length ? "Neue Fassung erstellen" : "Anschreiben erstellen"}
          </button>
          {generate.isPending && req.generator !== "template" && aiAvailable && (
            <p className="hint">Das dauert mit KI etwa 20 bis 60 Sekunden.</p>
          )}
        </section>
      </aside>

      <section className="studio__main" aria-label="Anschreiben">
        {letters.length > 0 && (
          <div className="versions" role="tablist" aria-label="Fassungen">
            {letters.map((l) => (
              <button
                key={l.id}
                type="button"
                role="tab"
                aria-selected={active?.id === l.id}
                className={`version ${active?.id === l.id ? "is-active" : ""}`}
                onClick={() => setActiveId(l.id)}
              >
                V{l.version}
                <span className="version__meta">{GENERATOR_LABEL[l.generator] ?? l.generator}</span>
                {l.status === "final" && <span className="version__final">final</span>}
              </button>
            ))}
          </div>
        )}
        {active ? (
          <LetterEditor key={active.id} letter={active} />
        ) : (
          <div className="empty studio__empty">
            <p className="empty__title">Noch kein Anschreiben</p>
            <p>Links Ton und Länge wählen und „Anschreiben erstellen“ drücken. Jede Fassung bleibt gespeichert.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function Choice<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="field">
      <legend>{label}</legend>
      <div className="segmented segmented--3">
        {options.map((o) => (
          <label key={o.value} className={value === o.value ? "is-active" : ""}>
            <input type="radio" checked={value === o.value} onChange={() => onChange(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function LetterEditor({ letter }: { letter: CoverLetter }) {
  const toast = useToast();
  const [body, setBody] = useState(letter.body);
  const update = useMutate((data: Partial<Pick<CoverLetter, "body" | "status">>) => api.updateLetter(letter.id, data));
  const dirty = body !== letter.body;

  useEffect(() => setBody(letter.body), [letter.body]);

  const save = (data: Partial<Pick<CoverLetter, "body" | "status">>, msg: string) =>
    update.mutate(data, { onSuccess: () => toast(msg), onError: (e) => toast(e.message, "error") });

  async function copy() {
    try {
      await navigator.clipboard.writeText(body);
      toast("In die Zwischenablage kopiert");
    } catch {
      toast("Kopieren nicht möglich, bitte Text markieren", "error");
    }
  }

  function download() {
    const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `Anschreiben_V${letter.version}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="editor">
      <p className="muted editor__meta">
        Fassung {letter.version} · {formatDateTime(letter.created_at)}
        {letter.model ? ` · ${letter.model}` : ""}
        {letter.edited ? " · von dir bearbeitet" : ""}
      </p>
      <textarea className="editor__text" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Text des Anschreibens" />
      <div className="editor__actions">
        <button type="button" className="btn btn--primary" disabled={!dirty || update.isPending} onClick={() => save({ body }, "Gespeichert")}>
          Speichern
        </button>
        <button type="button" className="btn" onClick={copy}>
          Kopieren
        </button>
        <button type="button" className="btn" onClick={download}>
          Als .txt
        </button>
        <button
          type="button"
          className={`btn ${letter.status === "final" ? "is-active" : ""}`}
          aria-pressed={letter.status === "final"}
          onClick={() =>
            save(
              { status: letter.status === "final" ? "draft" : "final", ...(dirty ? { body } : {}) },
              letter.status === "final" ? "Wieder Entwurf" : "Als finale Fassung markiert",
            )
          }
        >
          {letter.status === "final" ? "✓ Final" : "Als final markieren"}
        </button>
      </div>
    </div>
  );
}
