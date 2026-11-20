import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });
const failures = [];

async function inspectPage(path, viewport, label) {
  const page = await browser.newPage({ viewport });
  try {
    await page.goto(base + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(250);
    const dimensions = await page.evaluate(() => ({
      width: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    assert.ok(
      dimensions.documentWidth <= dimensions.width + 1 && dimensions.bodyWidth <= dimensions.width + 1,
      `${label} horizontal overflow: ${JSON.stringify(dimensions)}`
    );
    assert.ok(dimensions.height > 0, `${label} rendered an empty document`);
    return page;
  } catch (error) {
    failures.push(`${label}: ${error.message}`);
    await page.close();
    return null;
  }
}

try {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 820, height: 1180 },
    { width: 390, height: 844 },
  ]) {
    const label = `${viewport.width}x${viewport.height}`;

    const home = await inspectPage("/", viewport, `landing ${label}`);
    if (home) {
      try {
        await home.getByRole("heading", { name: /Run your properties with confidence/i }).waitFor();
        await home.getByRole("link", { name: /Create workspace/i }).first().waitFor();
        if (viewport.width < 768) {
          await home.getByRole("button", { name: "Open menu" }).click();
          await home.getByRole("link", { name: "Capabilities", exact: true }).waitFor();
        }
        await home.screenshot({ path: `artifacts/landing-${viewport.width}.png`, fullPage: true });
        if (viewport.width === 390) {
          await home.getByRole("button", { name: "First" }).click();
          await home.getByRole("button", { name: "101" }).click();
          await home.getByText("101", { exact: true }).first().waitFor();
        }
      } catch (error) {
        failures.push(`landing interactions ${label}: ${error.message}`);
      }
      await home.close();
    }

    const login = await inspectPage("/login", viewport, `login ${label}`);
    if (login) {
      try {
        const password = login.getByLabel("Password", { exact: true });
        await password.fill("example-password");
        await login.getByRole("button", { name: "Show password" }).click();
        assert.equal(await password.getAttribute("type"), "text");
        await login.getByRole("button", { name: "Hide password" }).click();
        assert.equal(await password.getAttribute("type"), "password");
        await login.screenshot({ path: `artifacts/login-${viewport.width}.png`, fullPage: true });
      } catch (error) {
        failures.push(`login interactions ${label}: ${error.message}`);
      }
      await login.close();
    }

    const register = await inspectPage("/register", viewport, `register ${label}`);
    if (register) {
      try {
        const password = register.getByLabel("Password", { exact: true });
        await password.fill("example-password");
        await register.getByRole("button", { name: "Show password" }).click();
        assert.equal(await password.getAttribute("type"), "text");
        await register.screenshot({ path: `artifacts/register-${viewport.width}.png`, fullPage: true });
      } catch (error) {
        failures.push(`registration interactions ${label}: ${error.message}`);
      }
      await register.close();
    }
    console.log(`PASS responsive smoke: ${label}`);
  }
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("All Chromium responsive smoke checks passed.");
}
