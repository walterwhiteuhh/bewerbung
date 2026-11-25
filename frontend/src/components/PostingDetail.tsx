import { useState, type FormEvent } from "react";
import { CompanyLogo } from "./CompanyLogo";
import { CompanySection } from "./CompanySection";
import { InsightsSection } from "./Insights";

import { api } from "../api/client";
import { useLetters, useMutate, usePosting } from "../api/hooks";
import type { Application, ApplicationStatus, PostingDetail as Posting } from "../api/types";
import { formatDate, formatDateTime, formatSalary, isoToLocalDate, localDateToIso } from "../lib/format";
import { EXITS, PIPELINE, REMOTE_LABEL, STATUS_LABEL } from "../lib/labels";
import { MetaLine, Priority, SourceTag, StatusPill } from "./Badges";
import { Dialog } from "./Dialog";
import { PostingDocuments } from "./Documents";
import { GENERATOR_LABEL, LetterStudio } from "./LetterStudio";
import { TagInput } from "./TagInput";
import { useToast } from "./Toast";

interface Props {
  id: number;
  onClose: () => void;
  onEdit: (p: Posting) => void;
  showClose: boolean;
  onOpenProfile: (tab?: "angaben" | "unterlagen") => void;
}

export function PostingDetail({ id, onClose, onEdit, showClose, onOpenProfile }: Props) {
  const { data: p, isLoading, error } = usePosting(id);
  const toast = useToast();
  const archive = useMutate((archived: boolean) => (archived ? api.archivePosting(id) : api.restorePosting(id)));

  if (isLoading) return <div className="detail detail--loading">Lade …</div>;
  if (error || !p) return <div className="detail empty">Stelle nicht gefunden.</div>;

  const app = p.application;
  const salary = formatSalary(p.salary_min, p.salary_max, p.salary_currency);

  return (
    <article className="detail">
      <header className="detail__head">
        {showClose && (
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zurück zur Liste">
            ←
          </button>
        )}
        <div className="detail__titles">
          <div className="card__top">
            {app && <StatusPill status={app.current_status} />}
            <SourceTag source={p.source} />
            {p.archived_at && <span className="tag">Archiviert</span>}
          </div>
          <div className="detail__title-row">
            {p.company && <CompanyLogo name={p.company.name} url={p.company.logo_url} size="md" />}
            <h2>{p.title}</h2>
          </div>
          <MetaLine className="detail__sub" items={[p.company?.name, p.location]} />
        </div>
        <div className="detail__actions">
          {p.url && (
            <a className="btn" href={p.url} target="_blank" rel="noreferrer noopener">
              Anzeige ↗
            </a>
          )}
          <button type="button" className="btn" onClick={() => onEdit(p)}>
            Bearbeiten
          </button>
        </div>
      </header>

      {app && <StatusControl key={app.id} app={app} />}

      <section className="facts">
        <Fact label="Gehalt" value={salary ?? "–"} />
        <Fact label="Arbeitsmodell" value={REMOTE_LABEL[p.remote_type]} />
        <Fact label="Anstellung" value={p.employment_type ?? "–"} />
        <Fact label="Beworben am" value={formatDate(app?.applied_at)} />
        <Fact label="Erfasst" value={formatDate(p.created_at)} />
        {p.external_id && <Fact label="Job-ID" value={p.external_id} />}
      </section>

      {p.company && <CompanySection company={p.company} />}

      <InsightsSection postingId={p.id} />

      <TagsSection posting={p} />

      <LetterSection posting={p} onOpenProfile={() => onOpenProfile("angaben")} />

      <PostingDocuments postingId={p.id} onManage={() => onOpenProfile("unterlagen")} />

      {app && <ApplicationFields key={app.id} app={app} />}

      {p.description && (
        <section className="section">
          <h3>Beschreibung</h3>
          <p className="prose">{p.description}</p>
        </section>
      )}

      {app && <Activity app={app} />}

      <footer className="detail__foot">
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() =>
            archive.mutate(!p.archived_at, {
              onSuccess: () => toast(p.archived_at ? "Wiederhergestellt" : "Archiviert"),
              onError: (e) => toast(e.message, "error"),
            })
          }
        >
          {p.archived_at ? "Wiederherstellen" : "Archivieren"}
        </button>
      </footer>
    </article>
  );
}

/** Kurzer Stand der Anschreiben; die eigentliche Arbeit passiert im großen Dialog. */
function LetterSection({ posting, onOpenProfile }: { posting: Posting; onOpenProfile: () => void }) {
  const [open, setOpen] = useState(false);
  const { data: letters = [] } = useLetters(posting.id);
  const final = letters.find((l) => l.status === "final");
  const latest = final ?? letters[0];
  return (
    <section className="section letter-teaser">
      <div className="letter-teaser__text">
        <h3>Anschreiben</h3>
        {latest ? (
          <p className="muted">
            {letters.length} {letters.length === 1 ? "Fassung" : "Fassungen"}
            {final ? ` · final: V${final.version}` : ` · zuletzt V${latest.version}`} ({GENERATOR_LABEL[latest.generator] ?? latest.generator})
          </p>
        ) : (
          <p className="muted">Passend zu Stelle, Beschreibung, Hashtags und Portal erstellen.</p>
        )}
      </div>
      <button type="button" className="btn btn--primary" onClick={() => setOpen(true)}>
        {latest ? "Öffnen" : "Anschreiben erstellen"}
      </button>
      <Dialog open={open} title={`Anschreiben · ${posting.title}`} onClose={() => setOpen(false)} wide>
        <LetterStudio posting={posting} onOpenProfile={onOpenProfile} />
      </Dialog>
    </section>
  );
}

/** Hashtags direkt in der Detailansicht pflegen; jede Änderung wird sofort gespeichert. */
function TagsSection({ posting }: { posting: Posting }) {
  const toast = useToast();
  const save = useMutate((tags: string[]) => api.updatePosting(posting.id, { tags }));
  return (
    <section className="section">
      <h3>Hashtags</h3>
      <TagInput
        value={posting.tags}
        onChange={(tags) => save.mutate(tags, { onError: (e) => toast(e.message, "error") })}
      />
      <p className="hint">Tipp: #hashtags in Notizen werden automatisch übernommen.</p>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusControl({ app }: { app: Application }) {
  const toast = useToast();
  const [target, setTarget] = useState<ApplicationStatus | null>(null);
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");
  const change = useMutate(() =>
    api.changeStatus(app.id, target!, note, date ? (localDateToIso(date) ?? undefined) : undefined),
  );
  const currentRank = PIPELINE.indexOf(app.current_status);

  function submit(e: FormEvent) {
    e.preventDefault();
    change.mutate(undefined, {
      onSuccess: () => {
        toast(`Status: ${STATUS_LABEL[target!]}`);
        setTarget(null);
        setNote("");
        setDate("");
      },
      onError: (err) => toast(err.message, "error"),
    });
  }

  return (
    <section className="section">
      <h3>Status</h3>
      <ol className="stepper">
        {PIPELINE.map((s, i) => (
          <li key={s} className={i < currentRank ? "is-done" : i === currentRank ? "is-current" : ""}>
            <button
              type="button"
              disabled={s === app.current_status}
              onClick={() => setTarget(s)}
              aria-pressed={target === s}
            >
              <span className="stepper__dot" aria-hidden />
              {STATUS_LABEL[s]}
            </button>
          </li>
        ))}
      </ol>
      <div className="exits">
        {EXITS.map((s) => (
          <button
            key={s}
            type="button"
            className={`chip status-${s} ${app.current_status === s ? "is-active" : ""}`}
            disabled={s === app.current_status}
            onClick={() => setTarget(s)}
          >
            <span className="dot" aria-hidden />
            {STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      {target && (
        <form className="status-form" onSubmit={submit}>
          <p>
            Wechsel zu <strong>{STATUS_LABEL[target]}</strong>
          </p>
          <input placeholder="Notiz (optional), z. B. Telefonat mit HR" value={note} onChange={(e) => setNote(e.target.value)} />
          <label className="inline">
            <span>Datum</span>
            <input type="date" value={date} max={isoToLocalDate(new Date().toISOString())} onChange={(e) => setDate(e.target.value)} />
          </label>
          <div className="row">
            <button type="button" className="btn btn--ghost" onClick={() => setTarget(null)}>
              Abbrechen
            </button>
            <button type="submit" className="btn btn--primary" disabled={change.isPending}>
              Übernehmen
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function ApplicationFields({ app }: { app: Application }) {
  const toast = useToast();
  const update = useMutate((data: Parameters<typeof api.updateApplication>[1]) => api.updateApplication(app.id, data));
  const save = (data: Parameters<typeof api.updateApplication>[1]) =>
    update.mutate(data, { onError: (e) => toast(e.message, "error") });

  return (
    <section className="section facts facts--edit">
      <div className="fact">
        <span>Priorität</span>
        <Priority value={app.priority} onChange={(priority) => save({ priority })} />
      </div>
      <label className="fact">
        <span>Nachfassen am</span>
        <input
          type="date"
          defaultValue={isoToLocalDate(app.follow_up_at)}
          onChange={(e) => save({ follow_up_at: localDateToIso(e.target.value) })}
        />
      </label>
      <label className="fact">
        <span>Ansprechpartner</span>
        <input
          defaultValue={app.contact_name ?? ""}
          placeholder="Name"
          onBlur={(e) => e.target.value !== (app.contact_name ?? "") && save({ contact_name: e.target.value || null })}
        />
      </label>
      <label className="fact">
        <span>E-Mail</span>
        <input
          type="email"
          defaultValue={app.contact_email ?? ""}
          placeholder="name@firma.de"
          onBlur={(e) => e.target.value !== (app.contact_email ?? "") && save({ contact_email: e.target.value || null })}
        />
      </label>
    </section>
  );
}

type Entry =
  | { kind: "event"; at: string; key: string; text: string; note: string | null; status: ApplicationStatus }
  | { kind: "note"; at: string; key: string; text: string };

/** Statuswechsel und Notizen als eine gemeinsame, neueste-zuerst Zeitleiste. */
function Activity({ app }: { app: Application }) {
  const toast = useToast();
  const [body, setBody] = useState("");
  const add = useMutate((text: string) => api.addNote(app.id, text));

  const entries: Entry[] = [
    ...app.events.map((e) => ({
      kind: "event" as const,
      at: e.occurred_at,
      key: `e${e.id}`,
      text: e.from_status ? `${STATUS_LABEL[e.from_status]} → ${STATUS_LABEL[e.to_status]}` : `Angelegt als ${STATUS_LABEL[e.to_status]}`,
      note: e.note,
      status: e.to_status,
    })),
    ...app.notes.map((n) => ({ kind: "note" as const, at: n.created_at, key: `n${n.id}`, text: n.body })),
  ].sort((a, b) => b.at.localeCompare(a.at));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    add.mutate(body, { onSuccess: () => setBody(""), onError: (err) => toast(err.message, "error") });
  }

  return (
    <section className="section">
      <h3>Verlauf und Notizen</h3>
      <form className="note-form" onSubmit={submit}>
        <textarea rows={2} placeholder="Notiz hinzufügen …" value={body} onChange={(e) => setBody(e.target.value)} />
        <button type="submit" className="btn btn--primary" disabled={add.isPending || !body.trim()}>
          Hinzufügen
        </button>
      </form>
      <ol className="timeline">
        {entries.map((e) => (
          <li key={e.key} className={`timeline__item timeline__item--${e.kind} ${e.kind === "event" ? `status-${e.status}` : ""}`}>
            <span className="timeline__dot" aria-hidden />
            <div>
              <p className={e.kind === "note" ? "prose" : "timeline__event"}>{e.text}</p>
              {e.kind === "event" && e.note && <p className="prose muted">{e.note}</p>}
              <time dateTime={e.at} className="muted">
                {formatDateTime(e.at)}
              </time>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
