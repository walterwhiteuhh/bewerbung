import { useState, type FormEvent } from "react";

import { api } from "../api/client";
import { useMutate, useProfile } from "../api/hooks";
import type { Profile } from "../api/types";
import { useToast } from "./Toast";

type Draft = Omit<Profile, "updated_at" | "skills"> & { skills: string };

const toDraft = (p: Profile): Draft => ({ ...p, skills: p.skills.join(", ") });

/** Eigene Angaben, aus denen Anschreiben entstehen. Wird einmal gepflegt und für jede Stelle genutzt. */
export function ProfileForm({ onDone }: { onDone: () => void }) {
  const { data, isLoading } = useProfile();
  if (isLoading || !data) return <p className="muted">Lade …</p>;
  return <ProfileFields initial={data} onDone={onDone} />;
}

function ProfileFields({ initial, onDone }: { initial: Profile; onDone: () => void }) {
  const toast = useToast();
  const [d, setD] = useState<Draft>(() => toDraft(initial));
  const save = useMutate((p: Omit<Profile, "updated_at">) => api.saveProfile(p));
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((s) => ({ ...s, [k]: v }));
  const text = (k: Exclude<keyof Draft, "skills">) => ({
    value: d[k] ?? "",
    onChange: (e: { target: { value: string } }) => set(k, e.target.value || null),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const skills = [...new Set(d.skills.split(/[,;\n]/).map((s) => s.trim()).filter(Boolean))];
    save.mutate(
      { ...d, skills },
      { onSuccess: () => (toast("Profil gespeichert"), onDone()), onError: (err) => toast(err.message, "error") },
    );
  }

  return (
    <form className="form" onSubmit={submit}>
      <p className="hint field--full">
        Nur was hier steht, darf im Anschreiben vorkommen. Je konkreter (Projekte, Zahlen, Tools), desto besser wird der Text.
      </p>
      <label className="field">
        <span>Name</span>
        <input autoComplete="name" {...text("full_name")} />
      </label>
      <label className="field">
        <span>Kurzprofil</span>
        <input placeholder="z. B. Data Scientist mit 5 Jahren Erfahrung" {...text("headline")} />
      </label>
      <label className="field">
        <span>E-Mail</span>
        <input type="email" autoComplete="email" {...text("email")} />
      </label>
      <label className="field">
        <span>Telefon</span>
        <input type="tel" autoComplete="tel" {...text("phone")} />
      </label>
      <label className="field field--full">
        <span>Adresse</span>
        <input autoComplete="street-address" {...text("address")} />
      </label>
      <label className="field field--full">
        <span>Über mich</span>
        <textarea rows={4} placeholder="Was du kannst, was du suchst, worauf du stolz bist" {...text("summary")} />
      </label>
      <label className="field field--full">
        <span>Skills (durch Komma getrennt)</span>
        <input placeholder="Python, SQL, Machine Learning, AWS" value={d.skills} onChange={(e) => set("skills", e.target.value)} />
      </label>
      <label className="field field--full">
        <span>Lebenslauf (Text)</span>
        <textarea rows={8} placeholder="Stationen, Projekte, Abschlüsse. Einfach aus dem CV hineinkopieren." {...text("cv_text")} />
      </label>
      <label className="field field--full">
        <span>Grußformel / Signatur</span>
        <textarea rows={2} placeholder={"Mit freundlichen Grüßen\nVorname Nachname"} {...text("signature")} />
      </label>
      <div className="form__actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          Profil speichern
        </button>
      </div>
    </form>
  );
}
