import { expect, test, type Page } from "@playwright/test";

/**
 * Layout-Regressionstests vom kleinen Smartphone bis 4K. Jede Breite prüft dieselben
 * Grundregeln: kein seitliches Scrollen, nichts ragt aus dem Bild, Touch-Ziele groß genug,
 * Overlays (Info-Karte, Dialoge) bleiben im Viewport.
 */
const VIEWPORTS = [
  { name: "iPhone SE", width: 320, height: 640, touch: true },
  { name: "Android", width: 360, height: 740, touch: true },
  { name: "iPhone 15", width: 390, height: 844, touch: true },
  { name: "iPhone Pro Max", width: 430, height: 932, touch: true },
  { name: "Tablet hoch", width: 768, height: 1024, touch: true },
  { name: "Tablet quer", width: 1024, height: 768, touch: true },
  { name: "Laptop", width: 1366, height: 768, touch: false },
  { name: "Full HD", width: 1920, height: 1080, touch: false },
  { name: "WQHD", width: 2560, height: 1440, touch: false },
  { name: "4K", width: 3840, height: 2160, touch: false },
] as const;

const MIN_TAP = 32; // px; Apple/Google empfehlen 44/48, kleine Inline-Elemente bekommen Polster

/** Elemente, die rechts oder links aus dem Viewport ragen, ohne in einem Scroll-Container zu liegen. */
async function layoutIssues(page: Page): Promise<string[]> {
  // Einblend-Animationen (Detail, Sheets) abwarten; Endlos-Animationen wie die Wellen nicht.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const issues: string[] = [];
    if (document.documentElement.scrollWidth > vw + 1) {
      issues.push(`Seite scrollt seitlich: ${document.documentElement.scrollWidth} > ${vw}`);
    }
    const clipped = (el: Element): boolean => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        const cs = getComputedStyle(p);
        if (["auto", "scroll", "hidden", "clip"].includes(cs.overflowX)) return true;
      }
      return false;
    };
    for (const el of document.querySelectorAll("body *")) {
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || cs.position === "fixed") continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      if ((r.right > vw + 1 || r.left < -1) && !clipped(el)) {
        issues.push(`${el.tagName.toLowerCase()}.${el.className} [${Math.round(r.left)}..${Math.round(r.right)}]`);
      }
    }
    return [...new Set(issues)].slice(0, 10);
  });
}

async function smallTapTargets(page: Page): Promise<string[]> {
  return page.evaluate((min) => {
    const out: string[] = [];
    for (const el of document.querySelectorAll<HTMLElement>("button, select, [role=button]")) {
      if (!el.offsetParent) continue;
      const r = el.getBoundingClientRect();
      if (r.height < min || r.width < min / 2) {
        out.push(`${el.className || el.tagName}: ${el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 20)} ${Math.round(r.width)}×${Math.round(r.height)}`);
      }
    }
    return [...new Set(out)];
  }, MIN_TAP);
}

async function expectInViewport(page: Page, selector: string): Promise<void> {
  const box = await page.locator(selector).first().boundingBox();
  const vp = page.viewportSize()!;
  expect(box, `${selector} sichtbar`).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.y).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(vp.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(vp.height + 1);
}

async function runSearch(page: Page): Promise<void> {
  await page.goto("/#/suche");
  await page.getByPlaceholder("z. B. Data Scientist, Python").fill("data");
  await page.locator("button[type=submit].btn--primary").click();
  await expect(page.locator(".card--hit").first()).toBeVisible();
}

for (const vp of VIEWPORTS) {
  test.describe(`${vp.name} ${vp.width}×${vp.height}`, () => {
    test.use({
      viewport: { width: vp.width, height: vp.height },
      hasTouch: vp.touch,
      isMobile: vp.width < 768,
    });

    test("Liste: kein Überlauf, Marke sichtbar, passende Aktion", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto("/#/");
      await expect(page.locator(".card").first()).toBeVisible();
      expect(await layoutIssues(page)).toEqual([]);
      await expectInViewport(page, ".brand");
      await expect(page.getByRole("heading", { name: "Anheuern" })).toBeVisible();
      if (vp.width < 640) await expectInViewport(page, ".fab");
      else await expect(page.locator(".fab")).toBeHidden();
      if (vp.width >= 1024) {
        // Ohne Auswahl zeigt die Detailspalte das Segelschiff statt einer leeren Fläche.
        await expect(page.getByRole("button", { name: /Segelschiff auf bewegter See/ })).toBeVisible();
      }
      if (vp.touch) expect(await smallTapTargets(page)).toEqual([]);
      expect(errors).toEqual([]);
    });

    test("Startseite: kein Überlauf, Button führt in die App", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1, name: /nächsten Job/ })).toBeVisible();
      expect(await layoutIssues(page)).toEqual([]);
      const cta = page.getByRole("link", { name: "Zur App" }).nth(1);
      await expectInViewport(page, ".lp-cta .lp-btn");
      if (vp.touch) expect((await cta.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await page.locator(".lp-ticker").evaluate((el) => el.scrollIntoView({ block: "center" }));
      await expectInViewport(page, ".lp-ticker");
      await page.locator(".lp-ticker__toggle").click(); // anhalten, Layout bleibt stabil
      expect(await layoutIssues(page)).toEqual([]);
      await cta.click();
      await expect(page.locator(".brand")).toBeVisible();
      expect(errors).toEqual([]);
    });

    test("Hashtags übergreifend: Firma taggen, Übersicht zeigt die Firma", async ({ page }) => {
      // Eigene Firma je Breite: alle Breiten teilen sich eine DB, parallele Tests dürfen sich nicht stören.
      const tag = `firma${vp.width}`;
      const created = await page.request.post("/api/postings", {
        data: { title: `Tag-Test ${vp.width}`, company_name: `Tagfirma ${vp.width} GmbH` },
      });
      expect(created.ok()).toBeTruthy();
      const { id } = await created.json();
      await page.goto(`/#/stelle/${id}`);
      const input = page.locator(".company__tags input");
      await input.scrollIntoViewIfNeeded();
      await input.fill(tag);
      await input.press("Enter");
      await expect(page.locator(".company__tags .hashtag", { hasText: `#${tag}` })).toBeVisible();
      expect(await layoutIssues(page)).toEqual([]);
      const resp = await page.request.get(`/api/tags/${tag}/overview`);
      expect(resp.ok()).toBeTruthy();
      expect((await resp.json()).company.map((c: { label: string }) => c.label)).toEqual([`Tagfirma ${vp.width} GmbH`]);
    });

    test("Suche: Hashtags an Treffern filtern, #tag im Suchfeld", async ({ page }) => {
      await page.goto("/#/suche");
      await page.getByPlaceholder(/#python/).fill("data #python");
      await page.locator("button[type=submit].btn--primary").click();
      await expect(page.locator(".card--hit").first()).toBeVisible();
      const bar = page.getByRole("toolbar", { name: "Nach Hashtag filtern" });
      await expect(bar).toBeVisible();
      expect(await layoutIssues(page)).toEqual([]);
      const total = await page.locator(".card--hit").count();
      const first = bar.getByRole("button").first();
      await first.click();
      await expect(first).toHaveAttribute("aria-pressed", "true");
      expect(await page.locator(".card--hit").count()).toBeLessThanOrEqual(total);
      expect(await layoutIssues(page)).toEqual([]);
      if (vp.touch) {
        const small = (await smallTapTargets(page)).filter((t) => t.includes("hashtag"));
        expect(small).toEqual([]);
      }
      await first.click(); // Filter wieder aus
      await expect(page.locator(".card--hit")).toHaveCount(total);
    });

    test("Verlauf: Menü bleibt im Bild, Auswahl entfernt Suchen", async ({ page }) => {
      page.on("dialog", (d) => void d.accept());
      // Alle Breiten teilen sich einen Server: eigener Suchbegriff, damit parallele Tests sich nicht stören.
      const term = `verlauf ${vp.width}`;
      await page.goto("/#/suche");
      await page.getByPlaceholder("z. B. Data Scientist, Python").fill(term);
      await page.locator("button[type=submit].btn--primary").click();
      await expect(page.locator(".card--hit").first()).toBeVisible();
      await page.reload(); // frische Ansicht: ohne geöffnetes Ergebnis zeigt die Suche den Verlauf
      await page.getByLabel("Verlauf durchsuchen").fill(term);
      const rows = page.locator(".recent__row");
      await expect(rows).toHaveCount(1);
      expect(await layoutIssues(page)).toEqual([]);
      await page.locator(".menu > summary").evaluate((el) => el.scrollIntoView({ block: "start" }));
      await page.locator(".menu > summary").click();
      await expectInViewport(page, ".menu__list");
      await page.locator(".menu > summary").click();
      await page.getByRole("button", { name: "Auswählen" }).click();
      await page.locator(".recent__check").first().check();
      expect(await layoutIssues(page)).toEqual([]);
      await page.getByRole("button", { name: "Entfernen" }).click();
      await expect(rows).toHaveCount(0);
    });

    test("Detail: lange Titel und Firmennamen brechen um", async ({ page }) => {
      await page.goto("/#/");
      await page.locator(".card", { hasText: "Plattform-Architektur" }).first().click();
      await expect(page.locator(".detail")).toBeVisible();
      expect(await layoutIssues(page)).toEqual([]);
      if (vp.touch) expect(await smallTapTargets(page)).toEqual([]);
    });

    test("Suche: Info-Karte bleibt im Bild", async ({ page }) => {
      await runSearch(page);
      expect(await layoutIssues(page)).toEqual([]);
      const trigger = page.locator(".card--hit .placehover").first();
      if (vp.touch) await trigger.tap();
      else await trigger.hover();
      const card = page.locator(".placecard");
      await expect(card).toBeVisible();
      // Einblend-Animation abwarten, sonst misst der Test die verschobene Startposition.
      await card.evaluate((el) => Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished)));
      await expectInViewport(page, ".placecard");
      if (vp.width < 640) await expect(card).toHaveClass(/is-sheet/);
      await page.keyboard.press("Escape");
      await expect(card).toBeHidden();
    });

    test("Dialoge passen in den Viewport", async ({ page }) => {
      await page.goto("/#/");
      await page.getByRole("button", { name: "Mein Profil" }).click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      await expectInViewport(page, "dialog[open]");
      expect(await layoutIssues(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Neue Stelle" }).locator("visible=true").first().click();
      await expectInViewport(page, "dialog[open]");
      expect(await layoutIssues(page)).toEqual([]);
    });
  });
}

test.describe("große Bildschirme", () => {
  test("4K nutzt die Breite und skaliert die Schrift", async ({ page }) => {
    await page.setViewportSize({ width: 3840, height: 2160 });
    await page.goto("/#/");
    const { root, app } = await page.evaluate(() => ({
      root: parseFloat(getComputedStyle(document.documentElement).fontSize),
      app: document.querySelector(".app")!.getBoundingClientRect().width,
    }));
    expect(root).toBeGreaterThanOrEqual(20);
    expect(app).toBeGreaterThan(3840 * 0.6);
    // Formularfelder wachsen mit, statt bei 16px Handy-Schrift zu bleiben.
    await page.goto("/#/suche");
    const input = await page
      .getByPlaceholder("z. B. Data Scientist, Python")
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(input).toBeGreaterThanOrEqual(root);
  });

  test("Laptop bleibt bei der Grundschrift", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/#/");
    const root = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
    expect(root).toBe(15);
  });
});

test.describe("Segelschiff", () => {
  test("animiert nur über Transforms", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/#/");
    const props = await page.evaluate(() =>
      [...document.querySelectorAll(".ship *")]
        .map((el) => getComputedStyle(el))
        .filter((cs) => cs.animationName !== "none")
        .map((cs) => cs.animationName),
    );
    expect(props.length).toBeGreaterThan(0);
    // Keyframes dürfen nur transform/opacity ändern (GPU-Compositing, kein Layout/Paint pro Frame).
    const animated = await page.evaluate(() => {
      const keys = new Set<string>();
      for (const sheet of document.styleSheets) {
        for (const rule of sheet.cssRules) {
          if (rule instanceof CSSKeyframesRule && rule.name.startsWith("ship-")) {
            for (const frame of rule.cssRules) {
              const style = (frame as CSSKeyframeRule).style;
              for (let i = 0; i < style.length; i++) keys.add(style[i]);
            }
          }
        }
      }
      return [...keys];
    });
    expect(animated.length).toBeGreaterThan(0);
    for (const prop of animated) expect(["transform", "opacity"]).toContain(prop);
  });

  test("steht still bei reduzierter Bewegung", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/#/");
    await expect(page.getByRole("button", { name: /Segelschiff auf bewegter See/ })).toBeVisible();
    const running = await page.evaluate(
      () => [...document.querySelectorAll(".ship *")].filter((el) => getComputedStyle(el).animationName !== "none").length,
    );
    expect(running).toBe(0);
  });

  test("Antippen ruft Ahoi und das Schiff springt", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/#/");
    const ship = page.getByRole("button", { name: /Segelschiff auf bewegter See/ });
    await ship.click();
    await expect(ship.locator(".ship__bubble")).toContainText("Ahoi!");
    await expect(ship.locator(".ship__hop.is-hopping")).toHaveCount(1);
    await ship.click();
    await expect(ship.locator(".ship__bubble")).toContainText("Leinen los!");
  });
});

test.describe("Statuswechsel mit Grund und Gehalt", () => {
  test("Absage speichert den Grund, Angebot das Gehalt; beides erscheint im Verlauf", async ({ page, request }) => {
    const created = await request.post("/api/postings", {
      data: { title: "Statusformular-Test", company_name: "Etikett GmbH", initial_status: "applied" },
    });
    expect(created.ok()).toBeTruthy();
    const posting = await created.json();
    try {
      await page.goto("/#/");
      await page.locator(".card", { hasText: "Statusformular-Test" }).first().click();
      await expect(page.locator(".detail")).toBeVisible();

      // Angebot: Gehaltsfeld, kein Grund
      await page.locator(".stepper button", { hasText: "Angebot" }).click();
      await expect(page.getByLabel("Grund")).toHaveCount(0);
      await page.getByPlaceholder("z. B. 65.000").fill("65.000");
      await page.getByRole("button", { name: "Übernehmen" }).click();
      await expect(page.locator(".timeline__detail", { hasText: "65.000" })).toBeVisible();

      // Absage: Grundauswahl, kein Gehalt
      await page.locator(".exits .chip", { hasText: "Absage" }).click();
      await expect(page.getByPlaceholder("z. B. 65.000")).toHaveCount(0);
      await page.getByLabel("Grund").selectOption({ label: "Gehalt passt nicht" });
      await page.getByRole("button", { name: "Übernehmen" }).click();
      await expect(page.locator(".timeline__detail", { hasText: "Gehalt passt nicht" })).toBeVisible();
    } finally {
      await request.post(`/api/postings/${posting.id}/archive`);
    }
  });
});
