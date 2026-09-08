// Run with Node and Playwright available through NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

test('Automatic lookup debounces input and fully spelled text commits without a model', { timeout: 60000 }, async () => {
  const browser=await chromium.launch({headless:true,
    ...(process.env.BCI_TEST_BROWSER ? {executablePath:process.env.BCI_TEST_BROWSER} : {}),
  });
  try{
    const page=await browser.newPage();
    const html=fs.readFileSync(path.join(__dirname,'../app/static/bci_speller.html'),'utf8');
    let calls=0;
    await page.route('**/*',route=>{
      if(new URL(route.request().url()).pathname==='/speller') return route.fulfill({contentType:'text/html',body:html});
      if(route.request().method()==='POST'){
        calls++;
        return route.fulfill({json:{candidates:[{candidate_id:'x',text:'물 줘'}]}});
      }
      return route.fulfill({json:{status:'healthy'}});
    });
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{
      state.partner='family';state.situation='general';showView('speller');renderKeyboard();
      el('autoPredict').checked=true;
    });
    await page.locator('#keyboard [data-c="ㅁ"]').click();
    await page.locator('#keyboard [data-c="ㅈ"]').click();
    await page.locator('.commit-candidate').waitFor();
    assert.equal(calls,1);
    assert.equal(await page.locator('#committed').textContent(),'');
    await page.evaluate(()=>{state.spelled={0:'물',1:'줘'};openRecoveryPanel();});
    await page.locator('#btnRecoveryPredict').click();
    assert.equal(await page.locator('#committed').textContent(),'물줘');
    assert.equal(calls,1);
  }finally{await browser.close();}
});

test('Public UI works offline, restores a draft, undoes commits and fits mobile', { timeout: 60000 }, async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.BCI_TEST_BROWSER ? {executablePath:process.env.BCI_TEST_BROWSER} : {}),
  });
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const html = fs.readFileSync(path.join(__dirname,'../app/static/bci_speller.html'),'utf8');
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    await page.route('**/*', route=>{
      const pathname=new URL(route.request().url()).pathname;
      if(pathname==='/speller') return route.fulfill({contentType:'text/html',body:html});
      if(pathname==='/health') return route.fulfill({json:{status:'healthy'}});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    await page.locator('#btnStart').click();
    await page.locator('#partnerGrid [data-v="family"]').click();
    await page.locator('#toStep2').click();
    await page.locator('#situationGrid [data-v="general"]').click();
    await page.locator('#toStep3').click();
    assert.equal(await page.evaluate(()=>state.sessionId),null);
    await page.locator('#directPanel summary').click();
    await page.locator('#directText').fill('잠깐 쉬고 싶어요.');
    await page.locator('#btnDirectCommit').click();
    assert.equal(await page.locator('#committed').textContent(),'잠깐 쉬고 싶어요.');
    await page.locator('#btnUndo').click();
    assert.equal(await page.locator('#committed').textContent(),'');
    assert.equal(await page.evaluate(()=>state.habitual.length),0);
    await page.locator('#directText').fill('다른 이야기를 하고 싶어요.');
    await page.locator('#btnDirectCommit').click();
    await page.locator('#context').fill('오늘 하루는 어땠어?');
    await page.locator('#keyboard [data-c="ㄷ"]').click();
    await page.locator('#keyboard [data-c="ㅇ"]').click();
    await page.locator('#keyboard [data-c="ㅈ"]').click();
    await page.reload();
    assert.equal(await page.locator('#committed').textContent(),'다른 이야기를 하고 싶어요.');
    assert.equal(await page.locator('#context').inputValue(),'오늘 하루는 어땠어?');
    assert.equal(await page.evaluate(()=>state.initials),'ㄷㅇㅈ');
    await page.locator('#btnPredict').click();
    await page.waitForFunction(()=>!document.querySelector('#btnPredict').disabled);
    assert.match(await page.locator('#candidates').textContent(),/직접 입력/);
    assert.equal(await page.evaluate(()=>state.initials),'ㄷㅇㅈ');
    await page.evaluate(()=>{
      state.latest=[{candidate_id:'a',text:'도와줘'},{candidate_id:'b',text:'들어줘'},{candidate_id:'c',text:'다음 주'}];
      renderCandidates({});
    });
    if(process.env.BCI_SCREENSHOT_DIR){
      fs.mkdirSync(process.env.BCI_SCREENSHOT_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.BCI_SCREENSHOT_DIR,'speller-desktop.png'),fullPage:true});
    }
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    if(process.env.BCI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.BCI_SCREENSHOT_DIR,'speller-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('Expired session retries once without losing input, context or FillMask constraints', { timeout: 60000 }, async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BCI_TEST_BROWSER ? { executablePath: process.env.BCI_TEST_BROWSER } : {}),
  });
  try {
    const page = await browser.newPage();
    const html = fs.readFileSync(path.join(__dirname, '../app/static/bci_speller.html'), 'utf8');
    const requests = [];
    await page.route('**/*', async route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/speller') return route.fulfill({ contentType: 'text/html', body: html });
      if (pathname.endsWith('/predict')) {
        requests.push({ pathname, body: route.request().postDataJSON() });
        if (pathname !== '/predict') {
          return route.fulfill({ status: 404, json: { detail: 'session not found' } });
        }
        return route.fulfill({ json: { candidates: [{ candidate_id: 'alt', text: '물 좀' }] } });
      }
      return route.fulfill({ json: { phrases: [] } });
    });
    await page.goto('http://bci.test/speller');
    await page.evaluate(() => {
      showView('speller');
      state.sessionId = 'expired';
      localStorage.setItem('bci_session_id', 'expired');
      state.partner = 'family';
      state.situation = 'general';
      state.initials = 'ㅁㅈ';
      state.committed = '도와줘';
      state.history = ['하나', '둘', '셋', '넷', '도와줘'];
      el('context').value = '목이 말라';
      renderBuffer();
      return openFillMask('물 줘', 1);
    });
    assert.deepEqual(requests.map(r => r.pathname), ['/session/expired/predict', '/predict']);
    assert.deepEqual(requests[0].body, requests[1].body);
    assert.equal(requests[1].body.current_sentence, '도와줘');
    assert.deepEqual(requests[1].body.recent_context, ['둘', '셋', '넷', '도와줘', '목이 말라']);
    assert.equal(requests[1].body.fill_mask_reference_text, '물 줘');
    assert.equal(requests[1].body.fill_mask_target_index, 1);
    assert.equal(await page.evaluate(() => state.initials), 'ㅁㅈ');
    assert.equal(await page.locator('#committed').textContent(), '도와줘');
    assert.equal(await page.evaluate(() => localStorage.getItem('bci_session_id')), null);
    await page.locator('.commit-candidate').click();
    assert.equal(await page.locator('#committed').textContent(), '도와줘 물 좀');
    await page.evaluate(() => { state.initials = 'ㅁㅈ'; return predict({}); });
    assert.equal(requests.at(-1).pathname, '/predict');
    assert.equal(requests.length, 3);
  } finally {
    await browser.close();
  }
});

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
