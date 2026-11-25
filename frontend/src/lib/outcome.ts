import type { ApplicationStatus, OutcomeReason } from "../api/types";

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
