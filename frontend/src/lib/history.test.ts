import { describe, expect, it } from "vitest";
import type { PrimaryCvPeriod, ProfileVersion } from "../api/types";
import { describePeriod, describeSkills, describeVersion, usageText } from "./history";

const version = (over: Partial<ProfileVersion> = {}): ProfileVersion => ({
  id: 2,
  created_at: "2026-11-02T10:00:00Z",
  is_first: false,
  changed_fields: ["skills", "headline"],
  skills_added: ["SQL"],
  skills_removed: ["Excel"],
  application_count: 0,
  ...over,
});

describe("history", () => {
  it("beschreibt Änderungen mit lesbaren Feldnamen", () => {
    expect(describeVersion(version())).toBe("Skills, Kurzprofil geändert");
    expect(describeVersion(version({ is_first: true }))).toBe("Erste Fassung");
    expect(describeVersion(version({ changed_fields: [] }))).toBe("Ohne inhaltliche Änderung");
    expect(describeVersion(version({ changed_fields: ["neu"] }))).toBe("neu geändert");
  });

  it("zeigt hinzugefügte und entfernte Skills", () => {
    expect(describeSkills(version())).toBe("+SQL −Excel");
    expect(describeSkills(version({ skills_added: [], skills_removed: [] }))).toBeNull();
  });

  it("beschreibt Zeiträume und Nutzung", () => {
    const p: PrimaryCvPeriod = {
      document_id: 1,
      title: "CV",
      archived: false,
      started_at: "2026-11-03T12:00:00Z",
      ended_at: null,
      application_count: 1,
    };
    expect(describePeriod(p)).toBe("03.11.2026 – heute");
    expect(describePeriod({ ...p, ended_at: "2026-11-12T12:00:00Z" })).toBe("03.11.2026 – 12.11.2026");
    expect(usageText(0)).toBe("keine Bewerbung damit");
    expect(usageText(1)).toBe("1 Bewerbung damit");
    expect(usageText(3)).toBe("3 Bewerbungen damit");
  });
});
