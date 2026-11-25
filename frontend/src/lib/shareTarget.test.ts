import { describe, expect, it } from "vitest";

import { extractSharedUrl } from "./shareTarget";

describe("extractSharedUrl", () => {
  it("nimmt den url-Parameter", () => {
    expect(extractSharedUrl("?url=https%3A%2F%2Fwww.stepstone.de%2Fstellenangebote--x")).toBe(
      "https://www.stepstone.de/stellenangebote--x",
    );
  });
  it("findet die URL im Text (LinkedIn)", () => {
    const text = encodeURIComponent("Schau mal: https://www.linkedin.com/jobs/view/123/ ");
    expect(extractSharedUrl(`?title=Job&text=${text}`)).toBe("https://www.linkedin.com/jobs/view/123/");
  });
  it("liefert null ohne URL", () => {
    expect(extractSharedUrl("?title=Hallo")).toBeNull();
    expect(extractSharedUrl("")).toBeNull();
  });
});
