import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Landing } from "./Landing";

describe("Landing", () => {
  it("zeigt den Slogan und führt per Link in die App", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("nächsten Job");
    const links = screen.getAllByRole("link", { name: /Zur App/ });
    expect(links.length).toBeGreaterThanOrEqual(2);
    for (const a of links) expect(a.getAttribute("href")).toBe("#/");
  });

  it("erklärt die Kernfunktionen", () => {
    render(<Landing />);
    for (const t of ["Alle Portale, ein Hafen", "Anschreiben mit KI", "Bewertungen im Mittel"]) {
      expect(screen.getByRole("heading", { name: t })).toBeTruthy();
    }
  });
});
