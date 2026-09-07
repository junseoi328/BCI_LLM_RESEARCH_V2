// Run with Node and Playwright available through NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

test('FillMask edits without committing and selects the displayed alternative', async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BCI_TEST_BROWSER ? { executablePath: process.env.BCI_TEST_BROWSER } : {}),
  });
  try {
    const page = await browser.newPage();
    const html = fs.readFileSync(path.join(__dirname, '../app/static/bci_speller.html'), 'utf8');
    const requests = [];
    let pending;
    await page.route('**/*', async route => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.pathname === '/speller') return route.fulfill({ contentType: 'text/html', body: html });
      const body = req.postDataJSON();
      requests.push({ path: url.pathname, body });
      if (url.pathname.endsWith('/predict')) {
        pending = route;
        return;
      }
      if (url.pathname.endsWith('/select')) {
        return route.fulfill({ json: { sentence: '물 좀', history: ['물 좀'] } });
      }
      return route.fulfill({ json: { phrases: [] } });
    });
    await page.goto('http://bci.test/speller');
    const setup = () => page.evaluate(() => {
      showView('speller');
      state.sessionId = 'test-session';
      state.initials = 'ㅁㅈ';
      state.committed = '';
      state.latest = [{ candidate_id: 'original', text: '물 줘' }];
      renderBuffer();
      renderCandidates({});
    });
    await setup();
    // Card padding and text whitespace must not commit a sentence.
    await page.locator('.candidate').click({ position: { x: 5, y: 5 } });
    await page.locator('.candidate .ct').dispatchEvent('click');
    assert.equal(requests.filter(r => r.path.endsWith('/select')).length, 0);
    await page.locator('.unit[data-u="1"]').click();
    await page.waitForFunction(() => document.querySelector('#fillmaskAlts').textContent.includes('대안 찾는 중'));
    await new Promise(resolve => {
      const poll = () => pending ? resolve() : setTimeout(poll, 10);
      poll();
    });
    assert.deepEqual(requests.at(-1).body.fill_mask_target_index, 1);
    assert.equal(requests.at(-1).body.fill_mask_reference_text, '물 줘');
    await page.keyboard.press('1');
    assert.equal(await page.locator('#committed').textContent(), '');
    assert.equal(requests.filter(r => r.path.endsWith('/select')).length, 0);
    await pending.fulfill({ json: { candidates: [
      { candidate_id: 'original', text: '물 줘' },
      { candidate_id: 'alternative', text: '물 좀' },
    ], recovery_mode: 'fill_mask' } });
    await page.locator('.alt').waitFor();
    assert.equal(await page.locator('#committed').textContent(), '');
    assert.equal(await page.locator('.candidate .ct').textContent(), '물 좀');
    await page.locator('.commit-candidate').click();
    await page.waitForFunction(() => document.querySelector('#committed').textContent === '물 좀');
    assert.equal(requests.find(r => r.path.endsWith('/select')).body.candidate_id, 'alternative');

    // Clearing input while recovery is in flight must discard the late response.
    pending = null;
    await setup();
    await page.locator('.unit[data-u="1"]').click();
    await new Promise(resolve => {
      const poll = () => pending ? resolve() : setTimeout(poll, 10);
      poll();
    });
    await page.locator('#btnClear').click();
    await pending.fulfill({ json: { candidates: [{ candidate_id: 'late', text: '물 좀' }] } });
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('.commit-candidate').count(), 0);
    assert.equal(await page.locator('#fillmaskBox').isVisible(), false);
    assert.equal(await page.evaluate(() => state.latest.length), 0);
  } finally {
    await browser.close();
  }
});
