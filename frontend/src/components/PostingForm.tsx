import { useState, type FormEvent } from "react";

import { ApiError, api } from "../api/client";
import { useMutate } from "../api/hooks";
import {
  REMOTE_TYPES,
  STATUSES,
  type ApplicationStatus,
  type PostingDetail,
  type PostingInput,
  type RemoteType,
  type ImportPreview,
  type SourceDetection,
} from "../api/types";
import { REMOTE_LABEL, SOURCE_LABEL, STATUS_LABEL } from "../lib/labels";
import { Priority } from "./Badges";
import { useToast } from "./Toast";

interface Props {
  initial?: PostingDetail;
  onDone: (id: number) => void;
  onOpenExisting: (id: number) => void;
}

const toInt = (v: string) => (v.trim() === "" ? null : Math.max(0, Math.round(Number(v))));

export function PostingForm({ initial, onDone, onOpenExisting }: Props) {
  const toast = useToast();
  const editing = initial !== undefined;
  const [f, setF] = useState({
    url: initial?.url ?? "",
    title: initial?.title ?? "",
    company_name: initial?.company?.name ?? "",
    location: initial?.location ?? "",
    remote_type: initial?.remote_type ?? ("unknown" as RemoteType),
    employment_type: initial?.employment_type ?? "",
    salary_min: initial?.salary_min?.toString() ?? "",
    salary_max: initial?.salary_max?.toString() ?? "",
    description: initial?.description ?? "",
    initial_status: "saved" as ApplicationStatus,
    priority: 3,
  });
  const [detection, setDetection] = useState<SourceDetection | null>(null);
  const [imported, setImported] = useState<ImportPreview | null>(null);
  const [importing, setImporting] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v }));

  async function detect(url: string) {
    if (url.trim().length < 8) return setDetection(null);
    try {
      const d = await api.detectSource(url);
      setDetection(d.duplicate_of === initial?.id ? { ...d, duplicate_of: null } : d);
    } catch {
      setDetection(null);
    }
  }

  /** Anzeige laden und nur leere Felder befüllen, damit nichts Getipptes überschrieben wird. */
  async function loadFromUrl(url: string) {
    if (!url.trim() || importing) return;
    setImporting(true);
    try {
      const preview = await api.importPreview(url);
      setImported(preview);
      setDetection(preview.detection.duplicate_of === initial?.id ? { ...preview.detection, duplicate_of: null } : preview.detection);
      setF((s) => ({
        ...s,
        title: s.title || preview.title || "",
        company_name: s.company_name || preview.company_name || "",
        location: s.location || preview.location || "",
        remote_type: s.remote_type === "unknown" ? preview.remote_type : s.remote_type,
        employment_type: s.employment_type || preview.employment_type || "",
        salary_min: s.salary_min || (preview.salary_min?.toString() ?? ""),
        salary_max: s.salary_max || (preview.salary_max?.toString() ?? ""),
        description: s.description || preview.description || "",
      }));
      if (preview.method !== "none") toast("Daten aus der Anzeige übernommen");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Import fehlgeschlagen", "error");
    } finally {
      setImporting(false);
    }
  }

  const save = useMutate((data: PostingInput) =>
    editing ? api.updatePosting(initial.id, data) : api.createPosting(data),
  );

  function submit(e: FormEvent) {
    e.preventDefault();
    const data: PostingInput = {
      title: f.title,
      url: f.url || null,
      company_name: f.company_name || null,
      location: f.location || null,
      remote_type: f.remote_type,
      employment_type: f.employment_type || null,
      salary_min: toInt(f.salary_min),
      salary_max: toInt(f.salary_max),
      description: f.description || null,
      ...(imported && !editing
        ? {
            raw_payload: imported.raw_payload,
            posted_at: imported.posted_at,
            ...(imported.salary_currency ? { salary_currency: imported.salary_currency } : {}),
          }
        : {}),
      ...(editing ? {} : { initial_status: f.initial_status, priority: f.priority }),
    };
    save.mutate(data, {
      onSuccess: (p) => {
        toast(editing ? "Gespeichert" : "Stelle angelegt");
        onDone(p.id);
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409 && typeof err.body.existing_id === "number") {
          setDetection((d) => (d ? { ...d, duplicate_of: err.body.existing_id as number } : d));
        }
        toast(err.message, "error");
      },
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <label className="field field--full">
        <span>Link zur Anzeige</span>
        <div className="url-row">
          <input
            type="url"
            inputMode="url"
            placeholder="https://www.linkedin.com/jobs/view/…"
            value={f.url}
            onChange={(e) => set("url", e.target.value)}
            onBlur={(e) => void detect(e.target.value)}
            onPaste={(e) => {
              const pasted = e.clipboardData.getData("text");
              void detect(pasted);
              if (!editing && !f.title) void loadFromUrl(pasted);
            }}
            autoFocus={!editing}
          />
          <button
            type="button"
            className="btn"
            onClick={() => void loadFromUrl(f.url)}
            disabled={!f.url.trim() || importing}
          >
            {importing ? <span className="spinner" aria-label="Lädt" /> : "Daten laden"}
          </button>
        </div>
        {detection && (
          <span className="hint">
            Erkannt: <strong>{SOURCE_LABEL[detection.source]}</strong>
            {detection.external_id && <> · Job-ID {detection.external_id}</>}
          </span>
        )}
        {imported && imported.method !== "json-ld" && (
          <span className="hint hint--warn">{imported.warnings.find((w) => !w.includes("bereits")) ?? ""}</span>
        )}
        {detection?.duplicate_of != null && (
          <span className="hint hint--warn">
            Diese Stelle ist schon erfasst.{" "}
            <button type="button" className="link" onClick={() => onOpenExisting(detection.duplicate_of!)}>
              Öffnen
            </button>
          </span>
        )}
      </label>

      <label className="field field--full">
        <span>Titel *</span>
        <input required maxLength={500} value={f.title} onChange={(e) => set("title", e.target.value)} />
      </label>
      <label className="field">
        <span>Firma</span>
        <input value={f.company_name} onChange={(e) => set("company_name", e.target.value)} />
      </label>
      <label className="field">
        <span>Ort</span>
        <input value={f.location} onChange={(e) => set("location", e.target.value)} />
      </label>

      <fieldset className="field field--full">
        <legend>Arbeitsmodell</legend>
        <div className="segmented">
          {REMOTE_TYPES.map((r) => (
            <label key={r} className={f.remote_type === r ? "is-active" : ""}>
              <input
                type="radio"
                name="remote_type"
                value={r}
                checked={f.remote_type === r}
                onChange={() => set("remote_type", r)}
              />
              {REMOTE_LABEL[r]}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="field">
        <span>Gehalt von (€/Jahr)</span>
        <input type="number" inputMode="numeric" min={0} step={1000} value={f.salary_min} onChange={(e) => set("salary_min", e.target.value)} />
      </label>
      <label className="field">
        <span>bis</span>
        <input type="number" inputMode="numeric" min={0} step={1000} value={f.salary_max} onChange={(e) => set("salary_max", e.target.value)} />
      </label>
      <label className="field">
        <span>Anstellung</span>
        <input placeholder="Vollzeit, Teilzeit, …" value={f.employment_type} onChange={(e) => set("employment_type", e.target.value)} />
      </label>

      {!editing && (
        <>
          <label className="field">
            <span>Status</span>
            <select value={f.initial_status} onChange={(e) => set("initial_status", e.target.value as ApplicationStatus)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <div className="field">
            <span>Priorität</span>
            <Priority value={f.priority} onChange={(v) => set("priority", v)} />
          </div>
        </>
      )}

      <label className="field field--full">
        <span>Beschreibung</span>
        <textarea rows={5} value={f.description} onChange={(e) => set("description", e.target.value)} />
      </label>

      <div className="form__actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {save.isPending ? "Speichere …" : editing ? "Speichern" : "Stelle anlegen"}
        </button>
      </div>
    </form>
  );
}
