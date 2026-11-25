import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import { Landing } from "./Landing";

const wrap = (ui: ReactElement) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);

describe("Landing", () => {
  it("zeigt den Slogan und führt per Link in die App", () => {
    wrap(<Landing />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("nächsten Job");
    const links = screen.getAllByRole("link", { name: /Zur App/ });
    expect(links.length).toBeGreaterThanOrEqual(2);
    for (const a of links) expect(a.getAttribute("href")).toBe("#/");
  });

  it("erklärt die Kernfunktionen", () => {
    wrap(<Landing />);
    for (const t of ["Alle Portale, ein Hafen", "Anschreiben mit KI", "Bewertungen im Mittel"]) {
      expect(screen.getByRole("heading", { name: t })).toBeTruthy();
    }
  });

  it("Ticker: Meldungen sind Links, der Knopf hält ihn an", async () => {
    wrap(<Landing />);
    const ticker = screen.getByRole("region", { name: "Neues aus dem Hafen" });
    expect(ticker.querySelectorAll("a[href]").length).toBeGreaterThan(6);
    // zweite Kopie für die Endlosschleife ist für Hilfstechnik versteckt
    expect(ticker.querySelectorAll("ul[aria-hidden]").length).toBe(1);
    const toggle = screen.getByRole("button", { name: "Ticker anhalten" });
    await userEvent.click(toggle);
    expect(ticker.hasAttribute("data-paused")).toBe(true);
    expect(screen.getByRole("button", { name: "Ticker fortsetzen" }).getAttribute("aria-pressed")).toBe("true");
  });
});
