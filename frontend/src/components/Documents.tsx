import { useRef, useState, type DragEvent } from "react";

import { api } from "../api/client";
import { useDocuments, useMutate, usePostingDocuments } from "../api/hooks";
import { DOCUMENT_KINDS, type DocumentInfo, type DocumentKind } from "../api/types";
import { formatDate } from "../lib/format";
import { DOCUMENT_KIND_LABEL } from "../lib/labels";
import { useToast } from "./Toast";

const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg";

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

function fileBadge(d: DocumentInfo): { text: string; cls: string } {
  if (d.content_type === "application/pdf") return { text: "PDF", cls: "doc__icon--pdf" };
  if (d.content_type.includes("wordprocessingml")) return { text: "DOCX", cls: "doc__icon--docx" };
  if (d.content_type.startsWith("image/")) return { text: "BILD", cls: "" };
  return { text: "TXT", cls: "" };
}

/** Ablage für Lebenslauf, Zeugnisse & Co. mit Drag-and-drop; Text wird serverseitig ausgelesen. */
export function DocumentsPanel() {
  const toast = useToast();
  const { data: docs = [], isLoading } = useDocuments();
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutate((f: File) => api.uploadDocument(f));
  const update = useMutate(({ id, ...data }: { id: number } & Parameters<typeof api.updateDocument>[1]) =>
    api.updateDocument(id, data),
  );
  const archive = useMutate((id: number) => api.archiveDocument(id));
  const useAsCv = useMutate((id: number) => api.useDocumentAsCv(id));

  function send(files: FileList | null) {
    for (const file of Array.from(files ?? [])) {
      setBusy((n) => n + 1);
      upload.mutate(file, {
        onSuccess: (d) =>
          toast(d.has_text ? `${d.title}: hochgeladen, Text erkannt` : `${d.title}: hochgeladen (ohne erkennbaren Text)`),
        onError: (e) => toast(`${file.name}: ${e.message}`, "error"),
        onSettled: () => setBusy((n) => n - 1),
      });
    }
  }

  function drop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    send(e.dataTransfer.files);
  }

  const err = (e: Error) => toast(e.message, "error");

  return (
    <div className="docs">
      <label
        className={`dropzone ${over ? "is-over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
      >
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        <strong>{busy > 0 ? "Lade hoch …" : "Dateien hierher ziehen oder auswählen"}</strong>
        <span className="hint">PDF, Word (.docx), Text oder Bild, bis 15 MB. Lebenslauf wird automatisch erkannt.</span>
        <input ref={input} type="file" accept={ACCEPT} multiple onChange={(e) => (send(e.target.files), (e.target.value = ""))} />
      </label>

      {isLoading ? (
        <p className="muted">Lade …</p>
      ) : docs.length === 0 ? (
        <p className="hint">Noch keine Unterlagen. Lade deinen Lebenslauf hoch, dann nutzen ihn auch die Anschreiben.</p>
      ) : (
        <ul className="doc-list">
          {docs.map((d) => {
            const badge = fileBadge(d);
            return (
              <li key={d.id} className="doc">
                <span className={`doc__icon ${badge.cls}`} aria-hidden>
                  {badge.text}
                </span>
                <div className="doc__head">
                  <a className="doc__title" href={api.documentUrl(d.id)} target="_blank" rel="noreferrer">
                    {d.title}
                  </a>
                  {d.is_primary && <span className="badge-primary">Haupt-CV</span>}
                </div>
                <span className="muted doc__meta">
                  {DOCUMENT_KIND_LABEL[d.kind]} · {formatBytes(d.size_bytes)}
                  {d.page_count ? ` · ${d.page_count} ${d.page_count === 1 ? "Seite" : "Seiten"}` : ""} · {formatDate(d.created_at)}
                  {!d.has_text && " · kein Text erkannt"}
                </span>
                {d.text_preview && <p className="doc__preview">{d.text_preview}</p>}
                <div className="doc__actions">
                  <select
                    aria-label="Art"
                    value={d.kind}
                    onChange={(e) => update.mutate({ id: d.id, kind: e.target.value as DocumentKind }, { onError: err })}
                  >
                    {DOCUMENT_KINDS.map((k) => (
                      <option key={k} value={k}>
                        {DOCUMENT_KIND_LABEL[k]}
                      </option>
                    ))}
                  </select>
                  {d.kind === "lebenslauf" && !d.is_primary && (
                    <button type="button" className="btn btn--small" onClick={() => update.mutate({ id: d.id, is_primary: true }, { onError: err })}>
                      Als Haupt-CV
                    </button>
                  )}
                  {d.has_text && d.kind === "lebenslauf" && (
                    <button
                      type="button"
                      className="btn btn--small"
                      onClick={() =>
                        useAsCv.mutate(d.id, { onSuccess: () => toast("Text ins Profilfeld „Lebenslauf“ übernommen"), onError: err })
                      }
                    >
                      Text ins Profil
                    </button>
                  )}
                  <a className="btn btn--small btn--ghost" href={api.documentUrl(d.id, true)}>
                    Download
                  </a>
                  <button
                    type="button"
                    className="btn btn--small btn--ghost"
                    onClick={() => archive.mutate(d.id, { onSuccess: () => toast(`${d.title} archiviert`), onError: err })}
                  >
                    Archivieren
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Auswahl, welche Unterlagen zu dieser Bewerbung gehören (wird sofort gespeichert). */
export function PostingDocuments({ postingId, onManage }: { postingId: number; onManage: () => void }) {
  const toast = useToast();
  const { data: all = [] } = useDocuments();
  const { data: attached = [] } = usePostingDocuments(postingId);
  const save = useMutate((ids: number[]) => api.setPostingDocuments(postingId, ids));
  const ids = attached.map((d) => d.id);

  const toggle = (id: number) =>
    save.mutate(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id], {
      onError: (e) => toast(e.message, "error"),
    });

  return (
    <section className="section">
      <h3>Unterlagen</h3>
      {all.length === 0 ? (
        <p className="hint">
          Noch keine Unterlagen hochgeladen.{" "}
          <button type="button" className="link-btn" onClick={onManage}>
            Jetzt hochladen
          </button>
        </p>
      ) : (
        <>
          <div className="doc-picks" role="group" aria-label="Unterlagen für diese Bewerbung">
            {all.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`chip ${ids.includes(d.id) ? "is-active" : ""}`}
                aria-pressed={ids.includes(d.id)}
                onClick={() => toggle(d.id)}
                title={DOCUMENT_KIND_LABEL[d.kind]}
              >
                {ids.includes(d.id) ? "✓ " : ""}
                {d.title}
              </button>
            ))}
          </div>
          <p className="hint">
            Markiere, was du mitschickst.{" "}
            <button type="button" className="link-btn" onClick={onManage}>
              Unterlagen verwalten
            </button>
          </p>
        </>
      )}
    </section>
  );
}
