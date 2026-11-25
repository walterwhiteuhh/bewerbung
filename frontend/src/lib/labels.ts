import type { ApplicationStatus, JobSource, RemoteType } from "../api/types";

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
  manual: "Manuell",
  other: "Andere",
};

export const REMOTE_LABEL: Record<RemoteType, string> = {
  onsite: "Vor Ort",
  hybrid: "Hybrid",
  remote: "Remote",
  unknown: "Unbekannt",
};
