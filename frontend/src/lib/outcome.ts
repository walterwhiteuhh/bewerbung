import type { ApplicationStatus, OutcomeReason, Stats } from "../api/types";
import { formatSalary } from "./format";
import { OUTCOME_REASON_LABEL } from "./labels";

/** Gründe, die zu einem Zielstatus sinnvoll sind (Backend akzeptiert sie nur bei Endzuständen/Angebot). */
const REASONS: Partial<Record<ApplicationStatus, OutcomeReason[]>> = {
  rejected: [
    "no_response",
    "rejected_screening",
    "rejected_interview",
    "position_filled",
    "salary_mismatch",
    "location_mismatch",
    "other",
  ],
  withdrawn: ["better_offer", "salary_mismatch", "location_mismatch", "own_decision", "other"],
};

export const reasonsFor = (status: ApplicationStatus): OutcomeReason[] => REASONS[status] ?? [];

/** Ein Gehalt kann nur bei Angebot oder Zusage erfasst werden. */
export const asksSalary = (status: ApplicationStatus): boolean => status === "offer" || status === "accepted";

/** Eingabe wie "65.000", "65000" oder "65 000" als ganze Zahl; ungültig/leer = undefined. */
export function parseSalary(input: string): number | undefined {
  const digits = input.replace(/[\s.']/g, "");
  if (!/^\d+$/.test(digits)) return undefined;
  const value = Number(digits);
  return value > 0 && value <= 10_000_000 ? value : undefined;
}

export interface OutcomeSummary {
  reasons: { key: string; label: string; count: number }[];
  /** z. B. "Ø 70.000 € (60.000 € – 80.000 €), 2 Angebote"; leer ohne genannte Gehälter. */
  salary: string | null;
}

/** Absagegründe und Angebotsgehälter aus den Kennzahlen für die Anzeige aufbereiten. */
export function outcomeSummary(stats: Stats | undefined): OutcomeSummary {
  const reasons = (stats?.by_reason ?? []).map((b) => ({
    key: b.key,
    label: OUTCOME_REASON_LABEL[b.key as OutcomeReason] ?? b.key,
    count: b.count,
  }));
  const top = stats?.offer_salaries[0];
  const salary = top
    ? `Ø ${formatSalary(top.median, top.median, top.currency)?.split(" – ")[0]}` +
      (top.count > 1 ? ` (${formatSalary(top.min, top.max, top.currency)})` : "") +
      `, ${top.count} ${top.count === 1 ? "Angebot" : "Angebote"}`
    : null;
  return { reasons, salary };
}
