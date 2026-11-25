import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { company, features, rating } from "../test/fixtures";
import { MetaLine, Priority } from "./Badges";
import { RatingBadge } from "./EmployerRating";
import { distanceLabel, FeatureChips } from "./Insights";
import { ShipScene } from "./ShipScene";
import { SocialLinks } from "./SocialLinks";

describe("Merkmale", () => {
  it("formatiert Entfernungen deutsch und kennzeichnet Schätzungen", () => {
    expect(distanceLabel(features({ distance_km: 3.94 }))).toBe("3,9 km");
    expect(distanceLabel(features({ distance_km: 87.4, distance_estimated: true }))).toBe("ca. 87 km");
    expect(distanceLabel(features())).toBeNull();
  });

  it("färbt Chips nach Radius, Passung und Arbeitgeber-Bewertung", () => {
    render(
      <FeatureChips
        features={features({
          distance_km: 120,
          within_max_distance: false,
          match_score: 0.8,
          company: company({ employer_rating: rating({ mean: 2.5 }) }),
        })}
      />,
    );
    expect(screen.getByText("120 km")).toHaveClass("feat--warn");
    expect(screen.getByText("Passt 80 %")).toHaveClass("feat--good");
    expect(screen.getByText("★ 2,5 Arbeitgeber")).toHaveClass("feat--warn");
  });

  it("rendert nichts ohne Merkmale", () => {
    const { container } = render(<FeatureChips features={features()} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Arbeitgeber-Bewertung", () => {
  it("zeigt Mittelwert und Quellen", () => {
    render(<RatingBadge rating={rating()} />);
    expect(screen.getByText("4,1")).toBeInTheDocument();
    expect(screen.getByText(/Mittel aus Glassdoor, kununu · 251 Bewertungen/)).toBeInTheDocument();
  });

  it("weist auf zu wenige Bewertungen hin, kompakt dagegen gar nicht", () => {
    const few = rating({ mean: null, sources: [], review_count: 0 });
    render(<RatingBadge rating={few} />);
    expect(screen.getByText(/Zu wenige Bewertungen/)).toBeInTheDocument();
    const { container } = render(<RatingBadge rating={few} compact />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Social-Media-Links", () => {
  it("ordnet Netze fest und öffnet sicher in neuem Tab", () => {
    render(<SocialLinks links={{ x: "https://x.com/acme", linkedin: "https://www.linkedin.com/company/acme" }} website="https://acme.de" />);
    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.textContent)).toEqual(["Website", "LinkedIn", "X"]);
    for (const a of links) {
      expect(a).toHaveAttribute("target", "_blank");
      expect(a.getAttribute("rel")).toContain("noopener");
    }
  });

  it("rendert nichts ohne Profile und Website", () => {
    const { container } = render(<SocialLinks links={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Bausteine", () => {
  it("MetaLine lässt leere Werte weg", () => {
    const { container } = render(<MetaLine items={["Hamburg", null, "", "Vollzeit"]} />);
    expect(within(container).getAllByText(/./).map((n) => n.textContent)).toEqual(["Hamburg", "Vollzeit"]);
  });

  it("Priorität ist per Klick änderbar und beschriftet", async () => {
    const onChange = vi.fn();
    render(<Priority value={2} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Priorität 4" }));
    expect(onChange).toHaveBeenCalledWith(4);
    expect(screen.getAllByRole("button")).toHaveLength(5);
  });

  it("Segelschiff ist zugänglich beschriftet und hat nahtlose Wellen", () => {
    render(<ShipScene />);
    const svg = screen.getByRole("img", { name: "Segelschiff auf bewegter See" });
    const waves = svg.querySelectorAll(".ship__wave");
    expect(waves).toHaveLength(3);
    // 8 Perioden à 60 = 480 = doppelte Szenenbreite, Voraussetzung für die Endlos-Animation
    for (const w of waves) expect(w.getAttribute("d")?.match(/q15/g)).toHaveLength(8);
  });
});
