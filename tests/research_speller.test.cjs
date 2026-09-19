const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function setup(handler) {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BCI_TEST_BROWSER
      ? { executablePath: process.env.BCI_TEST_BROWSER }
      : {}),
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const html = fs.readFileSync(
    path.join(__dirname, "../app/static/research_speller.html"),
    "utf8",
  );
  await page.route("**/*", (r) =>
    new URL(r.request().url()).pathname === "/speller/research"
      ? r.fulfill({ contentType: "text/html", body: html })
      : handler(r),
  );
  await page.goto("http://bci.test/speller/research");
  return { browser, page };
}

test("40-key loop composes Korean, learns separate units only at completion and exports no raw text", async () => {
  const { browser, page } = await setup((r) =>
    r.fulfill({ json: { candidates: [] } }),
  );
  try {
    assert.equal(await page.locator(".key").count(), 40);
    assert.equal(
      await page.evaluate(() =>
        [..."ㄱㅗㅐㄴㅊㅏㄴㅎㅇㅏ"].reduce(composeInput, ""),
      ),
      "괜찮아",
    );
    assert.equal(
      await page.evaluate(() =>
        [..."ㄷㅗㅇㅗㅏㅈㅜㅓ"].reduce(composeInput, ""),
      ),
      "도와줘",
    );
    await page.evaluate(() => {
      $("condition").value = "direct";
    });
    await page.locator("#target").fill("물 주세요");
    await page.locator("#start").click();
    await page.locator("#wordMode").click();
    await page.locator("#entry").fill("물");
    await page.locator("#literal").click();
    assert.equal(await page.evaluate(() => memory.word.length), 0);
    await page.locator("#entry").fill("잘못");
    await page.locator("#literal").click();
    await page.locator("#undo").click();
    await page.locator("#entry").fill("주세요");
    await page.locator("#literal").click();
    await page.locator("#finish").click();
    assert.deepEqual(
      await page.evaluate(() => memory.word.map((x) => x.text)),
      ["물", "주세요"],
    );
    assert.equal(
      await page.evaluate(() => memory.sentence[0].text),
      "물 주세요",
    );
    assert.equal(await page.evaluate(() => trials[0].cer), 0);
    assert.equal(await page.evaluate(() => trials[0].requests), 0);
    assert.equal(
      await page.evaluate(() => JSON.stringify(trials).includes("물")),
      false,
    );
    await page.reload();
    assert.equal(await page.evaluate(() => memory.word.length), 2);
    assert.equal(await page.evaluate(() => active), false);
  } finally {
    await browser.close();
  }
});

test("Remote results respect mode and target privacy; canceled stale results never replace current input", async () => {
  let payloads = [],
    release;
  const gate = new Promise((r) => (release = r));
  const { browser, page } = await setup(async (r) => {
    payloads.push(r.request().postDataJSON());
    if (payloads.length === 2) await gate;
    await r.fulfill({
      json: { candidates: [{ text: "문제" }, { text: "물 줘" }] },
    });
  });
  try {
    await page.locator("#target").fill("비밀 목표");
    await page.locator("#start").click();
    await page.locator("#wordMode").click();
    await page.locator("#entry").fill("ㅁㅈ");
    await page.locator("#lookup").click();
    await page.waitForFunction(() => !controller);
    assert.match(await page.locator("#candidates").textContent(), /문제/);
    assert.doesNotMatch(
      await page.locator("#candidates").textContent(),
      /물 줘/,
    );
    assert.equal(payloads[0].candidate_unit, "word");
    assert.equal(JSON.stringify(payloads).includes("비밀"), false);
    await page.locator("#lookup").click();
    assert.equal(payloads.length, 1);
    await page.locator("#entry").fill("ㄷㅇㅈ");
    await page.locator("#lookup").click();
    await page.waitForFunction(
      () => $("candidates").getAttribute("aria-busy") === "true",
    );
    await page.locator("#entry").fill("새 입력");
    release();
    await page.waitForTimeout(250);
    assert.doesNotMatch(
      await page.locator("#candidates").textContent(),
      /문제/,
    );
    assert.equal(await page.locator("#entry").inputValue(), "새 입력");
  } finally {
    release();
    await browser.close();
  }
});

test("Research guide and large-text layouts fit narrow screens", async () => {
  const { browser, page } = await setup((r) =>
    r.fulfill({ json: { candidates: [] } }),
  );
  try {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.locator("#start").click();
    await page.locator("#entry").fill("ㅁㅈ");
    await page.evaluate(() =>
      candidates([{ text: "물 주세요", source: "미리보기" }]),
    );
    if (process.env.BCI_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.BCI_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({
        path: path.join(process.env.BCI_SCREENSHOT_DIR, "research-desktop.png"),
        fullPage: true,
      });
    }
    await page.locator("#large").click();
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 850 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
    }
    await page.locator("#help").click();
    await page.keyboard.press("Tab");
    assert.equal(
      await page.evaluate(() => $("guide").contains(document.activeElement)),
      true,
    );
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#entry").inputValue(), "ㅁㅈ");
    if (process.env.BCI_SCREENSHOT_DIR)
      await page.screenshot({
        path: path.join(process.env.BCI_SCREENSHOT_DIR, "research-mobile.png"),
        fullPage: true,
      });
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
});
