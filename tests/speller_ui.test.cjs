// Run with Node and Playwright available through NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

// 기존 테스트는 40키 두벌식 자판 기준이다. 기본 자판(환자 실험용, 피그마)은 HTML('fig')로 받는다.
const HTML = (kb='k40') => fs.readFileSync(path.join(__dirname, '../app/static/bci_speller.html'), 'utf8')
  .replace('<head>', `<head><script>try{localStorage.setItem("bci_kb","${kb}")}catch(e){}</script>`);
const launch = () => chromium.launch({
  headless: true,
  ...(process.env.BCI_TEST_BROWSER ? { executablePath: process.env.BCI_TEST_BROWSER } : {}),
});

test('Input focus preserves drafts, candidate semantics and responsive 40-key layout', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:768}});
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML()} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();renderBuffer();});
    const before=await page.evaluate(()=>JSON.stringify(state));
    const guess=page.locator('#keyboard .key.cand.guess').first();
    assert.ok(await guess.count());
    assert.match(await guess.getAttribute('aria-label'),/후보 \d, 단어:/);
    await page.locator('#btnFocusInput').click();
    assert.equal(await page.locator('#conversationColumn').isVisible(),false);
    assert.equal(await page.evaluate(()=>JSON.stringify(state)),before);
    await page.waitForTimeout(600);
    assert.equal(await page.locator('#keyboard .key').count(),40);
    const bounds=await page.locator('#keyboard').boundingBox();
    if(process.env.BCI_SCREENSHOT_DIR){fs.mkdirSync(process.env.BCI_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BCI_SCREENSHOT_DIR,'speller-layout-check.png')});}
    assert.ok(bounds.y+bounds.height<=768,`keyboard bottom ${bounds.y+bounds.height}`);
    for(const width of [320,390,768,1440]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      assert.ok(await page.locator('#keyboard .key').first().evaluate(n=>n.getBoundingClientRect().height>=44));
    }
    await page.locator('#btnFocusInput').click();
    assert.equal(await page.locator('#conversationColumn').isVisible(),true);
    assert.equal(await page.evaluate(()=>JSON.stringify(state)),before);
    await page.locator('#btnFocusInput').click();
    await page.reload();
    assert.equal(await page.locator('#btnFocusInput').getAttribute('aria-pressed'),'true');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();renderBuffer();});
    await page.setViewportSize({width:1366,height:768});
    if(process.env.BCI_SCREENSHOT_DIR){fs.mkdirSync(process.env.BCI_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BCI_SCREENSHOT_DIR,'speller-focus-desktop.png')});}
  }finally{await browser.close();}
});

test('Guide isolates keyboard shortcuts, restores focus and supports large text on mobile', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:390,height:844}});
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';state.initials='ㅁㅈ';state.latest=[{candidate_id:'a',text:'물 줘'}];showView('speller');renderKeyboard();renderBuffer();renderCandidates({});});
    await page.locator('#btnGuide').click();
    assert.equal(await page.locator('#guideDialog').evaluate(d=>d.open),true);
    await page.keyboard.press('1');
    assert.equal(await page.locator('#committed').textContent(),'');
    assert.equal(await page.evaluate(()=>state.initials),'ㅁㅈ');
    for(let i=0;i<25;i++){
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>el('guideDialog').contains(document.activeElement)),true);
    }
    await page.locator('.guide-nav a[href="#guide-edit"]').click();
    assert.match(await page.locator('#guide-edit').textContent(),/FillMask/);
    assert.equal(await page.locator('#guideDialog').evaluate(d=>d.scrollWidth<=d.clientWidth),true);
    if(process.env.BCI_SCREENSHOT_DIR){fs.mkdirSync(process.env.BCI_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BCI_SCREENSHOT_DIR,'speller-guide-mobile.png')});}
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'btnGuide');
    await page.locator('#btnLargeText').click();
    assert.equal(await page.locator('#btnLargeText').getAttribute('aria-pressed'),'true');
    for(const width of [320,390,768,1440]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`no overflow at ${width}px`);
      assert.equal(await page.locator('.key').first().evaluate(n=>n.getBoundingClientRect().height>=44),true);
    }
    await page.reload();
    assert.equal(await page.locator('#btnLargeText').getAttribute('aria-pressed'),'true');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 40키 = 4행 × 10열, 두벌식 컴퓨터 자판 배치.
//   후보7 + 확정·글자삭제·띄기 3 | 초성 14(+⇧ 쌍자음 5) | 중성 12(+⇧ 겹모음 2) | ⇧ 1 | 부호 3
// 후보 선택이 키보드 안에 있어야 SSVEP로
// 옮길 수 있으므로(ChatBCI의 단어키 10, MindChat의 번호키 0~6과 같은 구조),
// 후보키의 존재와 후보↔키 결합은 UI의 계약이다.
test('40-key grid carries the candidates, and candidate keys commit what they display', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      const p=new URL(route.request().url()).pathname;
      if(p==='/speller') return route.fulfill({contentType:'text/html',body:html});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();renderBuffer();});

    assert.equal(await page.locator('#keyboard .key').count(),40,'40 keys');
    assert.equal(await page.locator('#keyboard .key.cho').count(),14,'기본 자음 14 (쌍자음은 ⇧)');
    assert.equal(await page.locator('#keyboard .key.jung').count(),12,'기본 모음 12 (ㅒㅖ 는 ⇧)');
    assert.equal(await page.locator('#keyboard .key.cand').count(),7);
    assert.equal(await page.locator('#keyboard .key.fn').count(),3,'확정·글자삭제·띄기');
    assert.equal(await page.locator('#keyboard .key.shift').count(),1);
    assert.equal(await page.locator('#keyboard .key.punct').count(),3,', . ?');

    // 자판과 같은 자리인가 — 2행 첫 다섯 칸이 ㅂㅈㄷㄱㅅ
    const row2=(await page.locator('#keyboard .key').allTextContents()).slice(10,15).map(t=>t.trim());
    assert.deepEqual(row2,['ㅂ','ㅈ','ㄷ','ㄱ','ㅅ'],'두벌식 상단 행');

    // ⇧ 를 켜면 쌍자음·겹모음으로 바뀌고, 한 글자 뒤 자동으로 풀린다
    await page.locator('#keyboard .key.shift').click();
    assert.equal(await page.locator('#keyboard .key.cho[data-v="ㅃ"]').count(),1,'⇧ 에서 ㅃ');
    assert.equal(await page.locator('#keyboard .key.jung[data-v="ㅒ"]').count(),1,'⇧ 에서 ㅒ');
    await page.locator('#keyboard .key.cho[data-v="ㅃ"]').click();
    assert.equal(await page.evaluate(()=>shiftOn),false,'한 글자 뒤 ⇧ 자동 해제');
    assert.equal(await page.evaluate(()=>state.initials),'ㅃ');
    await page.evaluate(()=>{state.initials='';state.spelled={};renderBuffer();});

    // 초성을 누르기 전에는 '다음에 할 말' 예측이 후보 자리를 채운다 (타건 0회 경로)
    const guesses=await page.locator('#candWords .cand.guess .tx').allTextContents();
    assert.ok(guesses.length>0,'next-word predictions fill the slots before any keypress');
    assert.equal(await page.locator('#candWords .cand.guess .cand-mark.guess').first().textContent(),'다음');

    // 단어 후보는 로컬이므로 서버가 죽어 있어도(503) 즉시 떠야 한다
    await page.locator('#keyboard .key.cho[data-v="ㅁ"]').click();
    await page.locator('#candWords .cand.word').first().waitFor();
    const shown=(await page.locator('#candWords .cand.word .tx').allTextContents());
    assert.ok(shown.length>0,'local word candidates render offline');
    assert.equal(await page.locator('#candKey0').isDisabled(),false);
    assert.equal((await page.locator('#candKeyW0').textContent()).trim(),shown[0],'candidate key shows its own candidate');

    // 중성까지 누르면 그 글자를 확정하고, 확정한 글자와 맞는 단어만 남는다
    await page.locator('#keyboard .key.jung[data-v="ㅜ"]').click();
    assert.equal((await page.locator('#iniDisplay').textContent()).trim(),'무');
    const pinned=await page.locator('#candWords .cand.word .tx').allTextContents();
    // 모음까지만 고른 글자는 받침을 후보가 채운다: 무 → 물·문·무슨 (초성+중성 '무'만 같으면 된다)
    const base=ch=>Math.floor((ch.charCodeAt(0)-0xAC00)/28);
    assert.ok(pinned.length && pinned.every(w=>base(w[0])===base('무')),`pinned syllable filters words: ${JSON.stringify(pinned)}`);

    // 후보키로 확정하면 그 키에 적혀 있던 단어가 그대로 들어간다
    const picked=pinned[0];
    await page.locator('#candKey0').click();
    await page.waitForFunction(t=>document.querySelector('#committed').textContent===t,picked);
    assert.equal(await page.evaluate(()=>state.initials),'');

    // 확정한 단어는 대화 로그에 '나' 발화로 쌓인다
    assert.deepEqual(await page.locator('#chatLog .chat-turn.me .tx').allTextContents(),[picked]);

    // 상대 입력은 별도 줄로만 들어오고 같은 로그에 누적된다
    await page.locator('#partnerText').fill('뭐 드릴까요');
    await page.locator('#btnPartnerSend').click();
    assert.deepEqual(await page.locator('#chatLog .chat-turn.partner .tx').allTextContents(),['뭐 드릴까요']);
    assert.equal(await page.locator('#partnerText').inputValue(),'');

    // 글자삭제/단어삭제
    await page.locator('#keyboard .key.cho[data-v="ㅈ"]').click();
    await page.locator('#keyboard .key.cho[data-v="ㅁ"]').click();
    await page.locator('#keyboard .key.fn.back').click();
    assert.equal(await page.evaluate(()=>state.initials),'ㅈ');
    // 단어삭제는 ⇧ 층에 있다 (자판의 Ctrl+Backspace 자리)
    await page.locator('#keyboard .key.shift').click();
    await page.locator('#keyboard .key.fn.delword').click();
    assert.equal(await page.evaluate(()=>state.initials),'');
    await page.locator('#keyboard .key.shift').click();
    await page.locator('#keyboard .key.fn.delword').click();
    assert.equal((await page.locator('#committed').textContent()).trim(),'','delword removes the last committed eojeol');

    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('Automatic lookup debounces input and fully spelled text commits without a model', { timeout: 60000 }, async () => {
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
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
    // 문장 후보는 언어 모델을 기다리지 않고 즉시(로컬 표현 사전에서) 떠야 한다
    const modelCall = page.waitForResponse(r => r.request().method()==='POST');
    await page.locator('#keyboard .key.cho[data-v="ㅁ"]').click();
    await page.locator('#keyboard .key.cho[data-v="ㅈ"]').click();
    await page.locator('#candSents .cand.sent').first().waitFor();
    assert.equal(calls,0,'local sentence candidates appear before any model call');

    // 두 번 연속 입력했어도 모델 조회는 한 번만 나간다 (디바운스)
    await modelCall;
    await page.waitForTimeout(400);
    assert.equal(calls,1);
    assert.equal(await page.locator('#committed').textContent(),'');

    // 모든 글자를 모음까지 확정하면 띄어쓰기로 바로 확정 — 언어 모델을 거치지 않는다
    await page.evaluate(()=>{state.initials='ㅁ';state.spelled={0:'물'};clearCandidates();renderBuffer();el('autoPredict').checked=false;});
    await page.locator('#keyboard .key.fn.space').click();
    await page.waitForFunction(()=>document.querySelector('#committed').textContent==='물');
    assert.equal(calls,1,'a fully spelled word commits with no extra model call');
  }finally{await browser.close();}
});

test('Public UI works offline, restores a draft, undoes commits and fits mobile', { timeout: 60000 }, async () => {
  const browser=await launch();
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const html = HTML();
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
    await page.locator('.settings-row details:last-child summary').click();
    await page.locator('#context').fill('오늘 하루는 어땠어?');
    await page.locator('#keyboard .key.cho[data-v="ㄷ"]').click();
    await page.locator('#keyboard .key.cho[data-v="ㅇ"]').click();
    await page.locator('#keyboard .key.cho[data-v="ㅈ"]').click();
    await page.reload();
    assert.equal(await page.locator('#committed').textContent(),'다른 이야기를 하고 싶어요.');
    assert.equal(await page.locator('#context').inputValue(),'오늘 하루는 어땠어?');
    assert.equal(await page.evaluate(()=>state.initials),'ㄷㅇㅈ');

    // 서버가 죽어 있어도 단어 후보는 계속 나오고, 안내가 직접 입력을 가리킨다
    await page.evaluate(()=>predict({}));
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('직접 입력'));
    assert.ok(await page.locator('#candWords .cand.word').count()>0,'word candidates survive an offline backend');
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
  const browser=await launch();
  try {
    const page = await browser.newPage();
    const html = HTML();
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
      // 대화는 화자와 함께 쌓이고, 그대로 모델 문맥이 된다
      state.history = [
        {who:'partner',text:'하나'},{who:'me',text:'둘'},{who:'partner',text:'셋'},
        {who:'me',text:'넷'},{who:'me',text:'도와줘'},
      ];
      el('context').value = '목이 말라';
      renderKeyboard(); renderBuffer();
      return openFillMask('물 줘', 1);
    });
    assert.deepEqual(requests.map(r => r.pathname), ['/session/expired/predict', '/predict']);
    assert.deepEqual(requests[0].body, requests[1].body);
    assert.equal(requests[1].body.current_sentence, '도와줘');
    assert.deepEqual(requests[1].body.recent_context, ['나: 둘','상대: 셋','나: 넷','나: 도와줘','상황: 목이 말라']);
    assert.equal(requests[1].body.fill_mask_reference_text, '물 줘');
    assert.equal(requests[1].body.fill_mask_target_index, 1);
    assert.equal(await page.evaluate(() => state.initials), 'ㅁㅈ');
    assert.equal(await page.locator('#committed').textContent(), '도와줘');
    assert.equal(await page.evaluate(() => localStorage.getItem('bci_session_id')), null);
    await page.locator('#candSents .cand.sent', {hasText:'물 좀'}).first().click();
    await page.waitForFunction(()=>document.querySelector('#committed').textContent==='도와줘 물 좀');
    await page.evaluate(() => { state.initials = 'ㅁㅈ'; return predict({}); });
    assert.equal(requests.at(-1).pathname, '/predict');
    assert.equal(requests.length, 3);
  } finally {
    await browser.close();
  }
});

test('FillMask edits without committing and selects the displayed alternative', {timeout:60000}, async () => {
  const browser=await launch();
  try {
    const page = await browser.newPage();
    const html = HTML();
    const requests = [];
    let pending;
    await page.route('**/*', async route => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.pathname === '/speller') return route.fulfill({ contentType: 'text/html', body: html });
      const body = req.postDataJSON();
      requests.push({ path: url.pathname, body });
      if (url.pathname.endsWith('/predict')) { pending = route; return; }
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
      state.history = [];
      state.latest = [{ candidate_id: 'original', text: '물 줘' }];
      renderKeyboard(); renderBuffer();
      renderCandidates({});
    });
    await setup();
    // 글자(unit)를 누르는 것은 '고치기'이지 '확정'이 아니다 — 절대 커밋되면 안 된다.
    await page.locator('#candSents .cand.sent', {hasText:'물 줘'}).first().locator('.unit[data-u="1"]').click();
    await page.waitForFunction(() => document.querySelector('#fillmaskAlts').textContent.includes('대안 찾는 중'));
    assert.equal(await page.locator('#committed').textContent(), '');
    assert.equal(requests.filter(r => r.path.endsWith('/select')).length, 0);
    await new Promise(resolve => { const poll=()=>pending?resolve():setTimeout(poll,10); poll(); });
    assert.deepEqual(requests.at(-1).body.fill_mask_target_index, 1);
    assert.equal(requests.at(-1).body.fill_mask_reference_text, '물 줘');
    await pending.fulfill({ json: { candidates: [
      { candidate_id: 'original', text: '물 줘' },
      { candidate_id: 'alternative', text: '물 좀' },
    ], recovery_mode: 'fill_mask' } });
    await page.locator('.alt').waitFor();
    assert.equal(await page.locator('#committed').textContent(), '');
    assert.ok((await page.locator('#candSents .cand.sent .tx').allTextContents()).some(t=>t.trim()==='물 좀'));
    await page.locator('#candSents .cand.sent', {hasText:'물 좀'}).first().click();
    await page.waitForFunction(() => document.querySelector('#committed').textContent === '물 좀');
    assert.equal(requests.find(r => r.path.endsWith('/select')).body.candidate_id, 'alternative');

    // 조회가 도중일 때 입력을 비우면 늦게 온 응답은 버려져야 한다.
    // (앞과 다른 글자를 골라야 조회 캐시에 걸리지 않고 실제로 요청이 나간다)
    pending = null;
    await setup();
    await page.locator('#candSents .cand.sent', {hasText:'물 줘'}).first().locator('.unit[data-u="0"]').click();
    await new Promise(resolve => { const poll=()=>pending?resolve():setTimeout(poll,10); poll(); });
    await page.locator('#btnClear').click();
    await pending.fulfill({ json: { candidates: [{ candidate_id: 'late', text: '물 좀' }] } });
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#candSents .cand.sent').count(), 0);
    assert.equal(await page.locator('#fillmaskBox').isVisible(), false);
    assert.equal(await page.evaluate(() => state.latest.length), 0);
  } finally {
    await browser.close();
  }
});

// Pseudo-online 실험 환경: 자극 창이 실제로 유지되는지, 오판독이 주입되는지,
// 결과가 엑셀에서 열리는 CSV로 나오는지 — 실험 결과의 신뢰성이 여기에 달려 있다.
test('Pseudo-online mode holds the stimulus window, injects misdecodes and exports CSV', {timeout:60000}, async () => {
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    await page.route('**/*',route=>{
      if(new URL(route.request().url()).pathname==='/speller') return route.fulfill({contentType:'text/html',body:html});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();renderBuffer();
      el('autoPredict').checked=false;el('expStim').value='300';el('expAcc').value='100';el('expOn').checked=true;
      // 동적 정지가 켜져 있으면 창이 120~300ms 로 줄어 아래 290ms 검사가 운에 달린다
      el('expStop').checked=false;});

    const t0=Date.now();
    await page.locator('#keyboard .key.cho[data-v="ㅁ"]').click();
    await page.waitForFunction(()=>state.initials==='ㅁ',null,{timeout:5000});
    assert.ok(Date.now()-t0>=290,'the stimulus window is actually held');
    assert.notEqual(await page.locator('#t2').textContent(),'–','SSVEP stage time is recorded');

    // 정확도를 낮추면 오판독이 주입돼 의도한 키와 다른 키가 입력된다
    await page.evaluate(()=>{el('expAcc').value='10';Math.random=()=>0.99;});
    await page.locator('#keyboard .key.cho[data-v="ㅎ"]').click();
    await page.waitForFunction(()=>document.querySelector('#expFlag').textContent.includes('오판독'),null,{timeout:5000});
    assert.equal(await page.evaluate(()=>state.initials.endsWith('ㅎ')),false,'a misdecode lands on a different key');

    assert.ok(await page.evaluate(()=>trials.length)>=2,'every selection is logged');
    const csv=await page.evaluate(()=>{
      const cols=["t","subject","exp_mode","key","type","decision_ms","stimulus_ms","decode_ms","total_ms","misdecode"];
      return {cols, sample:trials.at(-1)};
    });
    for(const c of ['decision_ms','stimulus_ms','decode_ms','total_ms','misdecode']){
      assert.ok(csv.sample[c]!==undefined,`trial records ${c}`);
    }
    await page.locator('#expPanel summary').click();
    const download=page.waitForEvent('download');
    await page.locator('#btnExportTrials').click();
    const file=await download;
    const out=path.join(require('node:os').tmpdir(),'bci-trials.csv');
    await file.saveAs(out);
    const text=fs.readFileSync(out,'utf8');
    assert.equal(text.charCodeAt(0),0xFEFF,'CSV starts with a UTF-8 BOM so Excel reads Korean');
    assert.match(text,/mean_s_per_selection/);
    assert.match(text,/decision_ms,stimulus_ms,decode_ms/);
  }finally{await browser.close();}
});

test('Physical keyboard drives the on-screen grid without hijacking text fields', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();renderBuffer();});

    // 두벌식 위치 그대로: a=ㅁ, n=ㅜ -> "무", w=ㅈ
    await page.keyboard.press('a');
    await page.keyboard.press('n');
    await page.keyboard.press('w');
    assert.equal(await page.evaluate(()=>state.initials),'ㅁㅈ','consonants land as 초성');
    assert.equal(await page.evaluate(()=>state.spelled[0]),'무','a vowel composes the syllable in place');

    // Shift 는 쌍자음
    await page.keyboard.press('Shift+q');
    assert.equal(await page.evaluate(()=>state.initials),'ㅁㅈㅃ','Shift reaches the double consonants');

    // 편집키
    await page.keyboard.press('Backspace');
    assert.equal(await page.evaluate(()=>state.initials),'ㅁㅈ','Backspace deletes one letter');

    // o·p 는 ㅐ·ㅔ (자판 그대로), Shift+o 는 ㅒ
    await page.evaluate(()=>{state.initials='';state.spelled={};renderBuffer();});
    await page.keyboard.press('a');            // ㅁ
    await page.keyboard.press('o');            // ㅐ -> "매"
    assert.equal(await page.evaluate(()=>state.spelled[0]),'매','o 는 ㅐ');

    // 문장부호 — , . / 자리 그대로, 완성된 단어 뒤에 붙는다
    await page.evaluate(()=>{state.committed='';state.initials='';state.spelled={};renderBuffer();});
    await page.keyboard.press('s'); await page.keyboard.press('k');   // ㄴ+ㅏ = 나
    await page.keyboard.press('Comma');
    assert.equal(await page.evaluate(()=>state.committed),'나,','쉼표가 띄어쓰기 없이 붙는다');
    await page.keyboard.press('Shift+Slash');
    assert.equal(await page.evaluate(()=>state.committed),'나,!','Shift+/ 는 느낌표');
    await page.evaluate(()=>{state.committed='';state.initials='';state.spelled={};renderBuffer();});

    // 눌린 키가 화면에서 짚인다
    await page.keyboard.down('a');
    assert.equal(await page.evaluate(()=>!!document.querySelector('.kb .key.kbd-hit')),true,'the pressed key is marked on screen');
    await page.keyboard.up('a');

    // 입력란에 포커스가 있으면 격자로 새지 않는다
    const before=await page.evaluate(()=>state.initials);
    await page.locator('#partnerText').click();
    await page.keyboard.type('안녕');
    assert.equal(await page.locator('#partnerText').inputValue(),'안녕','text goes to the focused field');
    assert.equal(await page.evaluate(()=>state.initials),before,'and not to the grid');

    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('A chosen word conditions the next candidates (bigrams chain across single-word commits)', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');

    const out=await page.evaluate(()=>{
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
      bgKey=null; markContextDirty();
      state.partner='family'; state.situation='general';
      showView('speller'); renderKeyboard();

      // 단어를 하나씩 고르는 실제 흐름. 예전에는 커밋마다 prev 가 "" 로
      // 초기화돼 "물 -> 좀" 같은 짝이 한 번도 기록되지 않았다.
      state.lastWord='';
      learnFromCommit('물');
      learnFromCommit('좀');
      learnFromCommit('주세요');

      const pairLearned = !!(learn.next['물'] && learn.next['물']['좀']);

      // 다시 "물"을 고른 직후라면 초성 0개 상태에서 "좀"이 후보에 떠야 한다
      state.lastWord='물'; bgKey=null;
      state.initials=''; state.spelled={}; state.latest=[];
      renderCandidatePanel();
      const guessed = slots.some(s=>s.text==='좀');

      // 초성을 눌러도 앞 단어 가산점이 계속 작용해야 한다
      state.initials='ㅈ'; renderCandidatePanel();
      const rankWithPrev = slots.findIndex(s=>s.text==='좀');
      state.lastWord=''; bgKey=null;
      renderCandidatePanel();
      const rankNoPrev = slots.findIndex(s=>s.text==='좀');

      // 앞 두 단어(트라이그램) — 같은 흐름을 한 번 더 태워 기록을 쌓는다
      state.lastWord=''; state.lastWord2='';
      learnFromCommit('물'); learnFromCommit('좀'); learnFromCommit('주세요');
      const triLearned = !!(learn.next2 && learn.next2['물\u0001좀'] && learn.next2['물\u0001좀']['주세요']);

      state.lastWord='좀'; state.lastWord2='물'; bgKey=null;
      state.initials=''; state.spelled={}; state.latest=[];
      renderCandidatePanel();
      const triFirst = slots.length && slots[0].text==='주세요';

      // 처음 보는 단어 뒤에서도 후보 칸이 비면 안 된다 (backoff)
      state.lastWord='존재하지않는단어'; state.lastWord2=''; bgKey=null;
      state.initials=''; renderCandidatePanel();
      const neverEmpty = slots.filter(s=>s.kind==='word').length>0;

      return {pairLearned, guessed, rankWithPrev, rankNoPrev, triLearned, triFirst, neverEmpty};
    });

    assert.equal(out.pairLearned,true,'선택한 단어끼리의 짝이 기록된다');
    assert.equal(out.guessed,true,'앞 단어만으로 다음 단어가 초성 0개에 뜬다');
    assert.ok(out.rankWithPrev>=0,'초성을 눌러도 후보에 남는다');
    assert.ok(out.rankNoPrev<0 || out.rankWithPrev<=out.rankNoPrev,
      '앞 단어가 있을 때의 순위가 없을 때보다 앞서거나 같다');
    assert.equal(out.triLearned,true,'앞 두 단어 문맥(트라이그램)이 기록된다');
    assert.equal(out.triFirst,true,'트라이그램이 걸리면 그 단어가 1번 자리에 온다');
    assert.equal(out.neverEmpty,true,'문맥이 하나도 안 걸려도 후보 칸이 비지 않는다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('Every form of context feeds the local candidate engine', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');

    const out=await page.evaluate(()=>{
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
      state.partner='family'; state.situation='general';
      state.history=[]; state.committed=''; state.lastWord=''; state.lastWord2='';
      el('context').value=''; showView('speller'); renderKeyboard(); markContextDirty();
      const foodCat=SEED_CATS.indexOf('food_drink');
      const w=()=>contextCats().get(foodCat)||0;

      const base=w();                                   // 아무 신호도 없을 때

      state.situation='meal'; markContextDirty();
      const bySituation=w();

      state.situation='general';
      el('context').value='식사 중이고 주스를 드시고 싶어 합니다'; markContextDirty();
      const byMemo=w();

      el('context').value='';
      state.history=[{who:'partner',text:'식사 하시겠어요?'}]; markContextDirty();
      const byPartner=w();

      // 상대가 쓴 단어 자체가 초성 검색에서 후보로 밀려 올라와야 한다(에코).
      // "물"은 한 글자 — AAC 에서 가장 자주 쓰는 말들이 대부분 한 글자다.
      state.history=[{who:'partner',text:'물 한 잔 드릴까요?'}];
      state.lastWord=''; state.lastWord2=''; markContextDirty();
      const echoHasMul = (echoMap().get('물')||0)>0;
      state.initials='ㅁ'; state.spelled={}; state.latest=[];
      renderCandidatePanel();
      const rankWithEcho=slots.findIndex(s=>s.text==='물');
      state.history=[]; markContextDirty();
      renderCandidatePanel();
      const rankNoEcho=slots.findIndex(s=>s.text==='물');

      return {base,bySituation,byMemo,byPartner,echoHasMul,rankWithEcho,rankNoEcho};
    });

    assert.equal(out.base,0,'신호가 없으면 가중치도 0');
    assert.ok(out.bySituation>0,'고른 상황이 문맥에 들어간다');
    assert.ok(out.byMemo>0,'직접 적은 상황 메모가 문맥에 들어간다');
    assert.ok(out.byPartner>0,'상대가 한 말이 문맥에 들어간다');
    assert.ok(out.bySituation>=out.byPartner,'직접 고른 값이 추론한 값보다 무겁다');
    assert.equal(out.echoHasMul,true,'상대가 쓴 단어가 에코 목록에 오른다');
    assert.ok(out.rankWithEcho>=0,'에코 단어는 초성 검색 후보에 뜬다');
    assert.ok(out.rankNoEcho<0 || out.rankWithEcho<=out.rankNoEcho,'에코가 있을 때 순위가 앞서거나 같다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 사전보다 긴 초성을 한 번에 치면(예: "뭐하고 있어" -> ㅁㅎㄱㅇㅇ) 단어·문장 두 줄이
// 모두 비어 막다른 길이 됐다. 맞는 가장 긴 앞부분까지 물러서고, 고르면 쓴 만큼만 지운다.
test('A too-long initial run falls back to the longest matching prefix instead of going empty', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'
      ?{contentType:'text/html',body:html}:{status:503,json:{detail:'offline'}}));
    await page.goto('http://bci.test/speller');

    const out=await page.evaluate(()=>{
      showView('speller'); el('autoPredict').checked=false;
      state.partner='family'; state.situation='general';
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};

      const probe=ini=>{ state.initials=ini; state.spelled={}; state.latest=[];
        renderCandidatePanel();
        return {n:slots.length, partial:slots.filter(s=>s.partial).length, top:slots[0]}; };

      const long=probe('ㅁㅎㄱㅇㅇ');        // 사전에 없는 5초성
      const junk=probe('ㅈㅋㅋㅌㅍㅎ');       // 아무것도 안 맞는 입력
      const short=probe('ㅁㅎ');            // 정상 경로 — 후퇴가 일어나면 안 된다

      // 부분 후보를 고르면 쓴 초성만 지우고 나머지는 버퍼에 남아야 한다
      state.initials='ㅁㅎㄱㅇㅇ'; state.spelled={}; state.latest=[];
      renderCandidatePanel();
      const k=slots.findIndex(s=>s.partial);
      const used=slots[k].partial;
      chooseSlot(k);
      return {long,junk,short,used};
    });

    assert.ok(out.long.n>0,'사전에 없는 긴 초성에도 후보가 남는다');
    assert.ok(out.long.partial>0,'그 후보들은 부분 일치로 표시된다');
    assert.ok(out.junk.n>0,'아무것도 안 맞는 입력에도 빈 줄이 되지 않는다');
    assert.equal(out.short.partial,0,'정상 경로에서는 후퇴하지 않는다');
    assert.ok(out.short.n>0);

    await page.waitForFunction(()=>state.committed!=='',null,{timeout:5000});
    assert.equal(await page.evaluate(()=>state.initials),'ㅁㅎㄱㅇㅇ'.slice(out.used),
      '부분 후보를 고르면 남은 초성이 버퍼에 남는다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 서버가 문장 후보를 못 줬을 때 "사전에 없음"과 같은 문구가 뜨면 사용자는 무엇을 해야
// 할지 알 수 없다. 실패는 실패라고 말하고, 다시 시도할 수 있어야 한다.
test('A failed sentence request says so and can be retried', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    let up=false, calls=0;
    await page.route('**/*',route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/speller') return route.fulfill({contentType:'text/html',body:html});
      if(path.endsWith('/predict')){ calls++;
        return up ? route.fulfill({json:{candidates:[{candidate_id:'c1',text:'뭐 하고 있어'}]}})
                  : route.fulfill({status:503,json:{detail:{code:'timeout',message:'x',retryable:true}}}); }
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
      state.initials='ㅁㅎㄱㅇㅇ';state.spelled={};renderBuffer();predict({});});

    await page.locator('#btnRetryLLM').waitFor({timeout:5000});
    assert.match(await page.locator('#candSents').textContent(),/불러오지 못했어요/,'실패를 실패라고 말한다');

    up=true;
    await page.locator('#btnRetryLLM').click();
    await page.locator('#candSents .cand.sent').first().waitFor({timeout:5000});
    assert.match(await page.locator('#candSents').textContent(),/뭐 하고 있어/,'다시 시도하면 후보가 뜬다');
    assert.equal(await page.locator('#btnRetryLLM').count(),0,'성공하면 실패 표시는 사라진다');
    assert.ok(calls>=2);
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 문장 후보는 빠른 경로(생성 1회, 순위 모델 생략)로 요청한다. 라이브 실측에서 중앙값
// 19.7s -> 7.7s. 한 번 실패한 뒤의 복구 요청만 넓게 뽑는 정밀 경로로 보낸다.
// 그리고 iPhone 너비(390px)에서 40키가 가로 스크롤 없이 한 화면에 들어와야 한다.
test('Sentence requests use the fast path and the keyboard fits an iPhone', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:390,height:844}});
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>route.fulfill(new URL(route.request().url()).pathname==='/speller'
      ?{contentType:'text/html',body:html}:{status:503,json:{detail:'offline'}}));
    await page.goto('http://bci.test/speller');
    const out=await page.evaluate(()=>{
      state.partner='family';state.situation='general';showView('speller');renderKeyboard();
      state.initials='ㅁㅈ';state.spelled={};renderBuffer();
      const kb=el('keyboard'), card=kb.closest('.kb-card');
      const keys=[...kb.querySelectorAll('.key')];
      const commit=kb.querySelector('.key.fn.commit');
      return {
        base:predictBody('ㅁㅈ').latency_strategy,
        keyword:predictBody('ㅁㅈ',{spelled_syllables:{0:'물'}}).latency_strategy,
        fillmask:predictBody('ㅁㅈ',{fill_mask_reference_text:'물 줘',fill_mask_target_index:1}).latency_strategy,
        overflow:card.scrollWidth-card.clientWidth,
        offscreen:keys.filter(k=>k.getBoundingClientRect().right>window.innerWidth+0.5).length,
        minW:Math.min(...keys.map(k=>k.getBoundingClientRect().width)),
        commitLabel:commit.getAttribute('aria-label'), commitText:commit.textContent,
      };
    });
    assert.equal(out.base,'fast');
    assert.equal(out.keyword,'balanced');
    assert.equal(out.fillmask,'balanced');
    assert.equal(out.offscreen,0,'40키가 모두 화면 안에 있다');
    assert.ok(out.overflow<=0,'키보드 카드가 가로로 스크롤되지 않는다');
    assert.ok(out.minW>=28,'키 너비 '+out.minW);
    assert.equal(out.commitLabel,'✓ 확정','기호만 보여도 스크린리더는 전체 이름을 읽는다');
    assert.equal(out.commitText,'✓ 확정');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 이어서 고른 단어는 대화 기록에서 한 발화다. 문장부호로 끝맺으면 다음 단어부터 새 발화.
// 서버 세션 문장은 부호를 모르므로 화면 문장이 그것으로 덮이면 안 된다.
test('Consecutive words form one turn and punctuation survives a server session', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/speller') return route.fulfill({contentType:'text/html',body:html});
      // 부호 없는 서버 문장을 돌려준다 — 화면은 이것을 따르면 안 된다
      if(path.endsWith('/select_text')) return route.fulfill({json:{sentence:'서버가 아는 문장'}});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    const out=await page.evaluate(async()=>{
      state.partner='family';state.situation='general';showView('speller');renderKeyboard();
      state.sessionId='s1';
      await commitText('낫겠네요'); await commitText('맛집은');
      const merged=state.history.map(h=>h.who+':'+h.text);
      await pressPunct('?');
      const afterPunct={committed:state.committed, turns:state.history.map(h=>h.who+':'+h.text)};
      await commitText('어디야');
      const next=state.history.map(h=>h.who+':'+h.text);
      el('btnUndo').click();
      return {merged, afterPunct, next, undone:state.history.map(h=>h.who+':'+h.text), committed:state.committed};
    });
    assert.deepEqual(out.merged,['me:낫겠네요 맛집은'],'단어마다 줄이 생기지 않는다');
    assert.equal(out.afterPunct.committed,'낫겠네요 맛집은?','서버 문장이 화면 문장을 덮지 않는다');
    assert.deepEqual(out.afterPunct.turns,['me:낫겠네요 맛집은?']);
    assert.deepEqual(out.next,['me:낫겠네요 맛집은?','me:어디야'],'부호로 끝맺으면 새 발화');
    assert.deepEqual(out.undone,['me:낫겠네요 맛집은?'],'되돌리기는 마지막 단어만 걷어낸다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 사전 층: 페이지와 따로 받는 약 40만 단어. 흔한 말은 바로 위에, 드문 사전 단어도
// 초성을 다 치고 글자 하나를 직접 쓰면 후보에 오른다.
test('Dictionary layer loads lazily and reaches rare dictionary words', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const dict=fs.readFileSync(path.join(__dirname,'../app/static/dict.txt'),'utf8');
    const rare=dict.trimEnd().split(/\r?\n/).reverse().find(l=>/^[가-힣]{2,4}$/.test(l));   // Windows 줄바꿈도 허용
    assert.ok(rare,'사전에서 빈도 정보 없는 단어를 선택한다');
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      const p=new URL(route.request().url()).pathname;
      if(p==='/speller') return route.fulfill({contentType:'text/html',body:html});
      if(p==='/speller/dict.txt') return route.fulfill({contentType:'text/plain',body:dict});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    const out=await page.evaluate(async(rare)=>{
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
      state.partner='friend';state.situation='general';
      const before=(state.initials='ㅊㄱ', state.spelled={}, renderCandidatePanel(), slots.map(s=>s.text));
      showView('speller'); await loadDict();
      const words=ini=>{state.initials=ini;state.spelled={};renderCandidatePanel();return slots.filter(s=>s.kind==='word').map(s=>s.text);};
      const common=words('ㅅㄹㅎ');
      // 앞 단어가 있으면 대사 n-gram 확률로 순위가 바뀐다
      state.lastWord='맛집은'; state.lastWord2='';
      const afterContext=words('ㅇㄸ');
      state.lastWord=''; 
      state.initials=choseongOf(rare); state.spelled={0:rare[0]}; renderCandidatePanel();
      return {size:DICT.size, common, afterContext, rareHit:slots.some(s=>s.text===rare), rare, before};
    },rare);
    assert.ok(out.size>300000,'사전 '+out.size);
    assert.ok(out.common.includes('사랑해'),out.common.join(','));
    assert.ok(out.afterContext.includes('어떠신가요'),'맛집은 + ㅇㄸ -> '+out.afterContext.join(','));
    assert.ok(out.rareHit,'드문 사전 단어 '+out.rare+' 도 후보에 오른다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 띄어쓰기 없이 문장 초성을 쭉 쳐도 띄어 쓴 문장이 나온다(화면 사례: ㅁㅈㅈㅅㅇㅈㅂ).
// 환자 표현에 있는 말은 그대로, 없는 말은 초성을 단어로 나눠 지은 문장이 뜬다.
test('Continuous initials become spaced sentences, patient phrases first', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const html=HTML();
    const dict=fs.readFileSync(path.join(__dirname,'../app/static/dict.txt'),'utf8');
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      const p=new URL(route.request().url()).pathname;
      if(p==='/speller') return route.fulfill({contentType:'text/html',body:html});
      if(p==='/speller/dict.txt') return route.fulfill({contentType:'text/plain',body:dict});
      return route.fulfill({status:503,json:{detail:'offline'}});
    });
    await page.goto('http://bci.test/speller');
    const out=await page.evaluate(async()=>{
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
      state.partner='family';state.situation='general';showView('speller');el('autoPredict').checked=false;
      await loadDict();
      const sents=ini=>{state.lastWord='';state.lastWord2='';state.initials=ini;state.spelled={};state.latest=[];
        renderCandidatePanel();return slots.filter(s=>s.kind==='sent').map(s=>s.text);};
      return {water:sents('ㅁㅈㅈㅅㅇㅈㅂ'), toilet:sents(choseongOf('화장실 가고 싶어요')),
              decoded:decodeSentences(choseongOf('가래 좀 뽑아주세요'),3)};
    });
    assert.equal(out.water[0],'물 좀 주세요 제발', out.water.join(' | '));
    assert.ok(out.toilet.includes('화장실 가고 싶어요'), out.toilet.join(' | '));
    assert.equal(out.decoded[0],'가래 좀 뽑아주세요','초성을 단어로 나눠 띄어 쓴다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('Enter after a mouse-picked candidate finishes the sentence instead of re-picking', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:768}});
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML()} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});
    for(const c of 'ㄷㅇㅈㅅㅇ') await page.click(`#keyboard .key[data-v="${c}"]`);
    await page.evaluate(()=>{state.latest=[{candidate_id:'s',text:'도와주세요'}];renderCandidates({});});
    const cands=await page.locator('#keyboard .key.cand').allTextContents();
    const i=cands.findIndex(t=>t.includes('도와주세요'));
    assert.ok(i>=0, cands.join(' | '));
    await page.locator('#keyboard .key.cand').nth(i).click();
    const picked=await page.evaluate(()=>state.committed);
    assert.equal(await page.evaluate(()=>state.initials),'');
    assert.match(await page.locator('#keyboard .key[data-v="commit"]').getAttribute('aria-label'),/엔터/);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#prevLines').textContent(),'','끝낸 문장은 입력 칸에서 빠진다');
    assert.equal(await page.locator('#committed').textContent(),'');
    assert.match(await page.locator('#chatLog .chat-turn.me').last().textContent(),new RegExp(picked.trim()),'대화 창으로 넘어간다');
    await page.keyboard.press('Enter');
    const s=await page.evaluate(()=>({c:state.committed,h:state.history.map(h=>h.text)}));
    assert.equal(s.c,'');
    assert.deepEqual(s.h,[picked]);
  }finally{await browser.close();}
});

test('SSVEP flicker still runs in experiment mode when the OS asks for reduced motion', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await (await browser.newContext({viewport:{width:1366,height:900},reducedMotion:'reduce'})).newPage();
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML()} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();
      el('expOn').checked=true;el('expOn').onchange();});
    await page.click('#keyboard .key[data-v="ㅁ"]');
    assert.equal(await page.locator('#keyboard .key.flicker').evaluate(n=>getComputedStyle(n).animationName),'ssvep');
  }finally{await browser.close();}
});

test('"원하는 말 없음" picks one syllable, keyboard vowel+✓ fills it and searches again', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:900}});
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML()} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});
    for(const c of 'ㄷㅇㅈㅅㅇ') await page.click(`#keyboard .key[data-v="${c}"]`);
    assert.equal(await page.locator('#btnNone').isVisible(),true);
    await page.keyboard.press('0');
    const idx=await page.evaluate(()=>state.jamoTarget);
    assert.ok(idx>=0 && idx<5);
    assert.match(await page.locator('#recoveryTitle').textContent(),/번째 글자/);
    // 단계식: 모음 하나로 바로 다시 찾는다(받침은 후보가 채운다)
    await page.click('#keyboard .key[data-v="ㅏ"]');
    const s=await page.evaluate(i=>({sp:state.spelled[i],vo:!!state.vowelOnly[i],ini:state.initials,target:state.jamoTarget,hist:state.history.length,title:el('recoveryTitle').textContent}),idx);
    assert.equal(s.sp, await page.evaluate(i=>composeSyllableJS(state.initials[i],'ㅏ',''),idx));
    assert.equal(s.vo,true,'모음까지만 고정');
    assert.equal(s.ini,'ㄷㅇㅈㅅㅇ','초성은 그대로');
    assert.equal(s.target,null);
    assert.equal(s.hist,0);
    assert.match(s.title,/다시 찾았습니다/);
    await page.keyboard.press('0');
    const [idx2,ask]=await page.evaluate(()=>[state.jamoTarget,spellAsk]);
    assert.ok(idx2!==idx || ask==='jong','다음에는 다른 글자의 모음, 또는 같은 글자의 받침');
  }finally{await browser.close();}
});

// 환자 실험용 자판(기본, 피그마 88:948·88:757): 자음 6열 + 아래 줄(문장 말하기·띄어쓰기·?·없음·확정) = 29키, 모음판 21+4 = 25키
test('Figma patient keyboard: 없음 swaps to the vowel board, vowel → 받침 → search again', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1920,height:1044}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML('fig')} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{localStorage.setItem('bci_none','auto');state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});   // v3.9 자동(단계식) 방식
    assert.equal(await page.locator('#keyboard .key').count(),29);
    assert.equal(await page.locator('#keyboard .key.cand').count(),5);
    assert.equal(await page.locator('.cand-card').isVisible(),false,'후보는 자판 첫 줄에만');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight),1044,'TV 1920×1044 한 화면');
    for(const c of 'ㄷㅇㅈㅅㅇ') await page.click(`#keyboard .key[data-v="${c}"]`);
    assert.ok(await page.evaluate(()=>slots.length)<=5);
    await page.click('#keyboard .key[data-v="none"]');
    const idx=await page.evaluate(()=>state.jamoTarget);
    assert.ok(idx>=0 && idx<5);
    assert.equal(await page.locator('#keyboard .key').count(),25,'모음 21 + 자모변환·글자·띄기·확정');
    assert.equal(await page.locator('#keyboard .key.jung').count(),21);
    assert.equal(await page.locator('#iniDisplay .wblock.target').count(),1,'완성할 글자를 빨갛게 표시');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight),1044);
    // 모음 하나 → 자음판으로 돌아와 바로 다시 찾음(선택 2번: 없음·모음)
    await page.click('#keyboard .key[data-v="ㅗ"]');
    assert.equal(await page.locator('#keyboard .key').count(),29);
    const s=await page.evaluate(i=>({sp:state.spelled[i],vo:!!state.vowelOnly[i],want:composeSyllableJS(state.initials[i],'ㅗ',''),ini:state.initials,tgt:state.jamoTarget,guide:el('kbGuide').textContent}),idx);
    assert.equal(s.sp,s.want); assert.equal(s.vo,true); assert.equal(s.ini,'ㄷㅇㅈㅅㅇ'); assert.equal(s.tgt,null);
    assert.match(s.guide,/다시 찾았습니다/);
    // 받침을 물을 때: 자음판에서 받침 하나, ✓ = 받침 없음
    await page.evaluate(i=>{ state.guided=true; state.jamoTarget=i; spellAsk='jong'; state.jamoMedial='ㅗ'; renderBuffer(); },idx);
    assert.match(await page.locator('#keyboard .key[data-v="commit"]').getAttribute('aria-label'),/받침 없음/);
    await page.click('#keyboard .key[data-v="ㄴ"]');
    assert.deepEqual(await page.evaluate(i=>[state.spelled[i],!!state.vowelOnly[i]],idx),[await page.evaluate(i=>composeSyllableJS(state.initials[i],'ㅗ','ㄴ'),idx),false]);
    // 다시 없음 → 다른 글자, ⌫ 로 취소하면 초성은 그대로
    await page.click('#keyboard .key[data-v="none"]');
    assert.notEqual(await page.evaluate(()=>state.jamoTarget),null);
    await page.click('#keyboard .key[data-v="back"]');
    assert.deepEqual(await page.evaluate(()=>[state.jamoTarget,state.initials,kbScreen]),[null,'ㄷㅇㅈㅅㅇ','cons']);
    // 자모변환(직접): 마지막 글자에 모음 하나 → 자음판으로 복귀
    await page.click('#btnReset');
    await page.click('#keyboard .key[data-v="ㅁ"]');
    await page.click('#keyboard .key[data-v="swap"]');
    await page.click('#keyboard .key[data-v="ㅜ"]');
    assert.deepEqual(await page.evaluate(()=>[state.spelled[0],kbScreen]),['무','cons']);
    // 설정에서 40키로 바꾸면 예전 자판
    await page.evaluate(()=>setKbLayout('k40'));
    assert.equal(await page.locator('#keyboard .key').count(),40);
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('요즘 이야깃거리: issues from /speller/news drive context only when chosen or asked about', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:900}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const now=new Date().toISOString(), u=n=>`https://www.yna.co.kr/view/AKR${n}`;
    const news={items:[{title:'한화 한국시리즈 우승',url:u(1),category:'스포츠',published_at:now,source:'연합뉴스'},
                       {title:'독감 유행 주의보',url:u(2),category:'건강',published_at:now,source:'연합뉴스'}],
      issues:[{keyword:'한화',words:['우승','한국시리즈'],category:'스포츠',count:3,score:2,titles:[{title:'한화 한국시리즈 우승',url:u(1),published_at:now}]},
              {keyword:'독감',words:['유행'],category:'건강',count:2,score:1,titles:[{title:'독감 유행 주의보',url:u(2),published_at:now}]}],
      trends:[['한화',3,2],['독감',2,1]],updated_at:now,unavailable:[]};
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      if(p==='/speller/news') return r.fulfill({json:news});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});
    await page.evaluate(()=>refreshNews());
    assert.equal(await page.locator('#newsItems .issue-btn').count(),2);
    assert.equal(await page.locator('#newsBadge').textContent(),'이슈 2');
    assert.equal(await page.evaluate(()=>newsContext()),'','고르지도 묻지도 않으면 뉴스는 문맥에 안 들어간다');
    // 일상어는 끼어들지 않는다
    await page.evaluate(()=>{state.history=[{who:'partner',text:'약 드셨어요?'}];});
    assert.equal(await page.evaluate(()=>newsContext()),'');
    // 분야를 물으면 그 분야 1위 이슈
    await page.evaluate(()=>{state.history=[{who:'partner',text:'요즘 야구 봤어?'}];});
    assert.match(await page.evaluate(()=>newsContext()),/한화/);
    // 고르면 그 이슈
    await page.evaluate(()=>{state.history=[];});
    await page.evaluate(()=>{el('newsPanel').open=true;});
    await page.locator('#newsItems .issue-btn',{hasText:'독감'}).click();
    assert.match(await page.evaluate(()=>newsContext()),/독감/);
    assert.ok(await page.evaluate(()=>echoMap().has('독감')),'고른 이슈의 말이 후보 쪽으로');
    await page.click('#btnNewsClear');
    assert.equal(await page.evaluate(()=>newsContext()),'');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 오선택(고른 직후 ⌫)이 잦으면 키를 크게 하자고 권하고, 누르면 환자 자판 키가 실제로 커진다.
// 대화 기록은 벤치(bench_dialog DIALOGS=)가 그대로 읽는 [[["them",..],["me",..]]] 꼴로 내려받는다.
test('Mis-selections suggest bigger keys and the dialog exports in bench format', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:768},acceptDownloads:true});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});
    const h0=await page.evaluate(()=>document.querySelector('#keyboard .key.cho').getBoundingClientRect().height);
    await page.evaluate(()=>{ for(let i=0;i<19;i++){ document.querySelector('#keyboard .key[data-v="ㄱ"]').click(); document.querySelector('#keyboard .key[data-v="back"]').click(); } });
    assert.ok(await page.locator('#misselTip').isHidden(),'20번 전에는 권하지 않는다');
    await page.evaluate(()=>{ document.querySelector('#keyboard .key[data-v="ㄱ"]').click(); document.querySelector('#keyboard .key[data-v="back"]').click(); });
    assert.equal(await page.evaluate(()=>trials.filter(t=>t.undone).length),20);
    await page.click('#btnMisselBig');
    const h1=await page.evaluate(()=>document.querySelector('#keyboard .key.cho').getBoundingClientRect().height);
    assert.ok(h1>=h0+12,`키가 커진다 ${h0}→${h1}`);
    await page.evaluate(()=>{ pushTurn('partner','물 줄까?'); pushTurn('me','물 조금만 줘'); el('expPanel').open=true; });
    const [d]=await Promise.all([page.waitForEvent('download'),page.click('#btnExportDialog')]);
    const body=JSON.parse(fs.readFileSync(await d.path(),'utf8'));
    assert.deepEqual(body,[[['them','물 줄까?'],['me','물 조금만 줘']]]);
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 실제 SSVEP: 보이는 키가 모두 서로 다른 주파수(8+0.2i Hz)로 동시에 깜빡이고, 자극 시작·끝이 이벤트로 남는다.
// OpenBCI Cyton 33바이트 패킷은 표본번호 순환(255→0)을 넘어 이어 세고 µV로 바꾼다. Esc는 보정을 바로 멈춘다.
test('Real SSVEP flickers every key at its own frequency and records Cyton EEG with events', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1366,height:900},acceptDownloads:true});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();el('expPanel').open=true;});
    await page.check('#expReal');
    assert.ok(await page.isChecked('#expOn'),'실제 자극을 켜면 실험 모드도 켜진다');
    await page.fill('#expStim','600');
    await page.click('#keyboard .key[data-v="ㄱ"]');
    await page.waitForTimeout(250);
    const mid=await page.evaluate(()=>({n:stimKeys().length, lit:stimKeys().filter(k=>k.style.background).length, dark:getComputedStyle(document.body).backgroundColor}));
    assert.equal(mid.lit,mid.n,'모든 키가 자극된다');
    assert.equal(mid.dark,'rgb(32, 32, 32)','자극 중 배경 #202020');
    await page.waitForTimeout(700);
    const ev=await page.evaluate(()=>eeg.events.filter(e=>e.type.startsWith('stim')).map(e=>[e.type,e.key,e.f]));
    assert.deepEqual(ev,[['stim_on','ㄱ',9.8],['stim_off','ㄱ',9.8]]);
    assert.equal(await page.evaluate(()=>state.initials),'ㄱ','자극이 끝나면 누른 키가 입력된다');
    assert.equal(await page.evaluate(()=>new Set(stimTable().map(k=>k.f)).size), mid.n, '키마다 다른 주파수');
    // 보정은 Esc로 멈춘다
    await page.evaluate(()=>{ runCalibration(1,1); });
    await page.waitForTimeout(400);
    await page.keyboard.press('Escape'); await page.waitForTimeout(900);
    assert.equal(await page.evaluate(()=>[calib.running, el('keyboard').classList.contains('ssvep-session')].join()),'false,false');
    // Cyton: 잡음 5바이트 + 표본번호 250..261(255에서 순환), ch1 = 1000(→22.352µV), 255번은 음수
    const rec=await page.evaluate(async()=>{
      const pk=(n,v)=>{ const a=new Uint8Array(33); a[0]=0xA0; a[1]=n&255; for(let c=0;c<8;c++){ const x=v&0xFFFFFF; a[2+3*c]=x>>16&255; a[3+3*c]=x>>8&255; a[4+3*c]=x&255; } a[32]=0xC0; return a; };
      const all=new Uint8Array(5+12*33); all.set([1,2,3,4,5]); for(let i=0;i<12;i++) all.set(pk(250+i,250+i===255?-1000:1000),5+i*33);
      let pos=0; const writes=[];
      const port={open:async()=>{}, close:async()=>{}, writable:{getWriter:()=>({write:async d=>writes.push(new TextDecoder().decode(d)),releaseLock(){}})},
        readable:{getReader:()=>({read:async()=>{ if(pos>=all.length) return new Promise(()=>{}); const v=all.slice(pos,pos+50); pos+=50; return {value:v,done:false}; },cancel:async()=>{}})}};
      eeg.rows=[]; await eegConnect(port); await new Promise(r=>setTimeout(r,200));
      return {writes, idx:eeg.rows.map(r=>r[2]), ch1:eeg.rows.map(r=>r[3]), dt:eeg.rows[1][0]-eeg.rows[0][0]};
    });
    assert.deepEqual(rec.writes,['s','b']);
    assert.deepEqual(rec.idx,[0,1,2,3,4,5,6,7,8,9,10,11],'255→0 순환을 이어 센다');
    assert.equal(rec.ch1[0],22.352); assert.equal(rec.ch1[5],-22.352); assert.equal(rec.dt,4);
    const [d]=await Promise.all([page.waitForEvent('download'),page.click('#btnEegExport')]);
    const csv=fs.readFileSync(await d.path(),'utf8').split('\n');
    assert.match(csv[0],/^#M .*"srate":250/);
    assert.ok(csv.some(l=>l.startsWith('#E ')&&l.includes('"stim_on"')));
    assert.ok(csv.includes('t_ms,arrival_ms,sample,ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8'));
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// v3.18 기본: '없음' → 번호 고르기 없이 맨 앞 글자부터 모음·받침으로 완성, 다시 '없음'이면 그다음 글자.
test('없음 completes syllables from the first one in order, vowel + 받침', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({viewport:{width:1920,height:1044}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'
      ? {contentType:'text/html',body:HTML('fig')} : {json:{status:'healthy'}}));
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');renderKeyboard();renderBuffer();});
    for(const c of 'ㄷㅇㅈㅅㅇ') await page.click(`#keyboard .key[data-v="${c}"]`);
    await page.click('#keyboard .key[data-v="none"]');
    // 번호 고르기 없이 맨 앞 글자부터 바로 모음판
    assert.deepEqual(await page.evaluate(()=>[state.pickPos,state.jamoTarget]),[null,0]);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight),1044);
    // ⌫ 는 취소
    await page.click('#keyboard .key[data-v="back"]');
    assert.deepEqual(await page.evaluate(()=>[state.jamoTarget,state.initials]),[null,'ㄷㅇㅈㅅㅇ']);
    // 다시 없음 → 첫 글자 → ㅗ → 받침 ㄴ → 그 글자가 완성되고 다시 찾는다
    await page.click('#keyboard .key[data-v="none"]');
    const pos=0;
    assert.equal(await page.evaluate(()=>state.jamoTarget),pos);
    assert.equal(await page.locator('#keyboard .key.jung').count(),21,'모음판');
    await page.click('#keyboard .key[data-v="ㅗ"]');
    assert.equal(await page.locator('#keyboard .key').count(),29,'받침은 자음판에서');
    assert.match(await page.locator('#kbGuide').textContent(),/받침/);
    await page.click('#keyboard .key[data-v="ㄴ"]');
    const r=await page.evaluate(i=>({sp:state.spelled[i],vo:!!state.vowelOnly[i],want:composeSyllableJS(state.initials[i],'ㅗ','ㄴ'),pick:state.pickPos,tgt:state.jamoTarget,lab:el('candKeyW0').textContent}),pos);
    assert.equal(r.sp,r.want); assert.equal(r.vo,false); assert.equal(r.pick,null); assert.equal(r.tgt,null);
    assert.doesNotMatch(r.lab,/번째/,'후보키는 다시 후보');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 이름 기억: 상대가 말한 드문 말(민수)·부르는 꼴(지수씨)은 이름으로 남고, 두 번 나오면 잊지 않는다.
// "누구 만났어?"엔 첫 단어로 이름, "걔"는 가장 최근 이름. ㅋㅇㅎ은 자막 인명(키요하루)이 아니라 쾌유해.
test('Names are remembered, answer 누구 questions and resolve 걔; odd subtitle names stay behind', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const dict=fs.readFileSync(path.join(__dirname,'../app/static/dict.txt'),'utf8');
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      if(p==='/speller/dict.txt') return r.fulfill({contentType:'text/plain',body:dict});
      return r.fulfill({status:503,json:{}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(async()=>{await loadDict(); try{localStorage.clear()}catch(e){} learn={word:{},next:{},next2:{},phrase:{},ctx:{},names:{},day:today()};
      state.partner='family';state.situation='general';el('autoPredict').checked=false;showView('speller');});
    const r=await page.evaluate(()=>{
      const W=ini=>{ state.initials=ini; return localWords(5,ini).map(x=>x.text); };
      const out={kyh:W('ㅋㅇㅎ')};
      pushTurn('partner','어제 민수 만났어? 지수씨도 왔대');
      out.names=Object.keys(learn.names).sort();
      state.initials=''; state.lastWord=''; state.lastWord2='';
      pushTurn('partner','누구 만났어?'); markContextDirty(); out.who=localWords(5,'').map(x=>x.text);
      pushTurn('partner','걔 요즘 어때?'); markContextDirty(); out.pron=echoMap().has(lastName());
      state.history=[]; markContextDirty(); out.ms=W('ㅁㅅ');
      pushTurn('partner','민수 또 왔어'); saveLearn(); loadLearn(); out.n=learn.names['민수'].n;
      return out; });
    assert.equal(r.kyh[0],'쾌유해',r.kyh.join(','));
    assert.ok(!r.kyh.includes('키요하루'));
    assert.deepEqual(r.names,['민수','지수']);
    assert.ok(['민수','지수'].includes(r.who[0]), r.who.join(','));
    assert.equal(r.pron,true);
    assert.equal(r.ms[0],'민수','초성을 끝까지 치면 이름이 맨 앞');
    assert.equal(r.n,2,'두 번 나온 이름은 저장되어 남는다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// AI 문장 추천 + 띄어 친 초성 → /choose: 어절마다 초성이 정확히 맞는 로컬 단어 목록을 보내고, 고른 문장이 문장 칸에 뜬다.
test('Spaced initials send a word lattice to /choose and show the chosen sentence', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    let sent=null;
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      if(p==='/choose'){ sent=JSON.parse(r.request().postData()); return r.fulfill({json:{candidates:[{candidate_id:'ch1',text:'물 좀 주세요',rank:1}],source:'lattice'}}); }
      if(p==='/predict') return r.fulfill({status:500,json:{detail:'should not be called'}});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';el('autoPredict').checked=true;showView('speller');renderKeyboard();renderBuffer();});
    await page.evaluate(()=>{ state.initials='ㅁㅈㅈㅅㅇ'; state.breaks=[1,2]; renderBuffer(); });
    await page.evaluate(()=>predict({}));
    assert.ok(sent && sent.slots.length===3, JSON.stringify(sent));
    assert.ok(sent.slots[0].includes('물') && sent.slots[1].includes('좀') && sent.slots[2].length>0, JSON.stringify(sent.slots));   // 사전 없이 도는 테스트라 목록이 짧다
    assert.ok(sent.slots.every((ws,i)=>ws.every(w=>w.length===[1,1,3][i])),'어절 길이까지 맞는 단어만');
    assert.ok((await page.evaluate(()=>slots.map(s=>s.text))).includes('물 좀 주세요'));
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// LSL 다리(Ganglion 4채널 200Hz): ws 메시지의 LSL 시각을 브라우저 시계로 옮겨 기록하고, CSV는 채널 수만큼 열을 낸다.
test('LSL bridge records Ganglion samples with aligned times and exports 4 channels', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage({acceptDownloads:true});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{ window.WebSocket=class{ constructor(u){ this.url=u; window.__ws=this; setTimeout(()=>{ this.onopen&&this.onopen();
        this.onmessage({data:JSON.stringify({meta:{name:'obci_eeg1',srate:200,n:4}})});
        this.onmessage({data:JSON.stringify({now:100.0,ts:[99.990,99.995],x:[[1,2,3,4],[5,6,7,8]]})}); },10); }
      close(){ this.onclose&&this.onclose(); } }; });
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    await page.evaluate(()=>{state.partner='family';state.situation='general';showView('speller');renderKeyboard();el('expPanel').open=true;});
    await page.click('#btnLslConnect'); await page.waitForTimeout(100);
    const r=await page.evaluate(()=>({url:window.__ws.url, n:eeg.rows.length, dev:eeg.device, sr:eeg.srate, dt:eeg.rows[1][0]-eeg.rows[0][0], lag:eeg.rows[1][1]-eeg.rows[1][0], ch:eeg.rows[1].slice(3)}));
    assert.equal(r.url,'ws://127.0.0.1:8765'); assert.equal(r.n,2); assert.equal(r.dev,'LSL obci_eeg1'); assert.equal(r.sr,200);
    assert.ok(Math.abs(r.dt-5)<0.01,'표본 간격 5ms(LSL 시각 차이)'); assert.ok(Math.abs(r.lag-5)<0.01,'마지막 표본은 받기 5ms 전');
    assert.deepEqual(r.ch,[5,6,7,8]);
    const [d]=await Promise.all([page.waitForEvent('download'),page.click('#btnEegExport')]);
    const csv=fs.readFileSync(await d.path(),'utf8').split('\n');
    assert.match(csv[0],/"srate":200/); assert.ok(csv.includes('t_ms,arrival_ms,sample,ch1,ch2,ch3,ch4'));
    await page.click('#btnLslConnect');
    assert.equal(await page.evaluate(()=>eeg.connected),false);
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

// 로컬 문장 복원이 어설프면(어절당 log10 확률 < -3) AI 해독 문장이 문장 칸을 먼저 차지하고, 확실하면 로컬이 남는다.
test('AI decode takes the sentence slot only when the local decode is unsure', {timeout:60000}, async()=>{
  const browser=await launch();
  try{
    const page=await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
      if(p==='/speller') return r.fulfill({contentType:'text/html',body:HTML('fig')});
      return r.fulfill({json:{status:'healthy',words:[]}});});
    await page.goto('http://bci.test/speller');
    const r=await page.evaluate(()=>{ state.partner='family';state.situation='general';showView('speller');
      const real=decodeSentences;
      const run=lp=>{ window.decodeSentences=()=>{ lastDecodeLp=[lp]; return ['로컬 문장']; };
        state.initials='ㄹㅋㅁㅈㅁ'; state.breaks=[]; state.latest=[{candidate_id:'ch1',text:'에이아이 문장'}];
        const out=sentenceSlots(1).map(x=>x.text); window.decodeSentences=real; return out[0]; };
      return {sure:run(-1.2), unsure:run(-5.0)}; });
    assert.equal(r.sure,'로컬 문장'); assert.equal(r.unsure,'에이아이 문장');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});
