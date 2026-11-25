import type { ApplicationStatus, JobSource, DocumentKind, OfferType, OutcomeReason, RemoteType, WorkTime } from "../api/types";

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  saved: "Gemerkt",
  applied: "Beworben",
  in_review: "In Prüfung",
  interview: "Interview",
  offer: "Angebot",
  accepted: "Angenommen",
  rejected: "Absage",
  withdrawn: "Zurückgezogen",
};

/** Hauptpfad des Funnels; Absage/Zurückgezogen sind Seitenausgänge. */
export const PIPELINE: ApplicationStatus[] = ["saved", "applied", "in_review", "interview", "offer", "accepted"];
export const EXITS: ApplicationStatus[] = ["rejected", "withdrawn"];

export const SOURCE_LABEL: Record<JobSource, string> = {
  linkedin: "LinkedIn",
  stepstone: "Stepstone",
  xing: "XING",
  indeed: "Indeed",
  arbeitsagentur: "Arbeitsagentur",
  glassdoor: "Glassdoor",
  personio: "Personio",
  greenhouse: "Greenhouse",
  lever: "Lever",
  softgarden: "softgarden",
  join: "JOIN",
  workday: "Workday",
  adzuna: "Adzuna",
  jooble: "Jooble",
  arbeitnow: "Arbeitnow",
  remotive: "Remotive",
  manual: "Manuell",
  other: "Andere",
};

export const REMOTE_LABEL: Record<RemoteType, string> = {
  onsite: "Vor Ort",
  hybrid: "Hybrid",
  remote: "Remote",
  unknown: "Unbekannt",
};

export const WORK_TIME_LABEL: Record<WorkTime, string> = {
  vollzeit: "Vollzeit",
  teilzeit: "Teilzeit",
  minijob: "Minijob",
  schicht: "Schicht/Nacht/WE",
};

export const OFFER_TYPE_LABEL: Record<OfferType, string> = {
  arbeit: "Arbeitsstelle",
  ausbildung: "Ausbildung / Duales Studium",
  praktikum: "Praktikum / Trainee",
  selbststaendig: "Selbstständigkeit",
};

export const DOCUMENT_KIND_LABEL: Record<DocumentKind, string> = {
  lebenslauf: "Lebenslauf",
  zeugnis: "Zeugnis",
  zertifikat: "Zertifikat",
  anschreiben: "Anschreiben",
  sonstiges: "Sonstiges",
};

export const OUTCOME_REASON_LABEL: Record<OutcomeReason, string> = {
  no_response: "Nie Rückmeldung",
  rejected_screening: "Absage nach Unterlagen",
  rejected_interview: "Absage nach Gespräch",
  position_filled: "Stelle besetzt",
  salary_mismatch: "Gehalt passt nicht",
  location_mismatch: "Ort passt nicht",
  better_offer: "Besseres Angebot",
  own_decision: "Eigene Entscheidung",
  other: "Sonstiges",
};
