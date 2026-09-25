// Run with Node and Playwright available through NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const HTML = () => fs.readFileSync(path.join(__dirname, '../app/static/bci_speller.html'), 'utf8');
const launch = () => chromium.launch({
  headless: true,
  ...(process.env.BCI_TEST_BROWSER ? { executablePath: process.env.BCI_TEST_BROWSER } : {}),
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

// 40키 = 초성19 + 중성10 + 후보7 + 기능4. 후보 선택이 키보드 안에 있어야 SSVEP로
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
    assert.equal(await page.locator('#keyboard .key.cho').count(),19);
    assert.equal(await page.locator('#keyboard .key.jung').count(),10);
    assert.equal(await page.locator('#keyboard .key.cand').count(),7);
    assert.equal(await page.locator('#keyboard .key.fn').count(),4);

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
    assert.ok(pinned.every(w=>w.startsWith('무')),`pinned syllable filters words: ${JSON.stringify(pinned)}`);

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
    await page.locator('#keyboard .key.fn.delword').click();
    assert.equal(await page.evaluate(()=>state.initials),'');
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
      el('autoPredict').checked=false;el('expStim').value='300';el('expAcc').value='100';el('expOn').checked=true;});

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
      learn={word:{},next:{},phrase:{},ctx:{},day:today()};
      bgKey=null; primedCats=new Set(); mineCats=new Set();
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

      return {pairLearned, guessed, rankWithPrev, rankNoPrev};
    });

    assert.equal(out.pairLearned,true,'선택한 단어끼리의 짝이 기록된다');
    assert.equal(out.guessed,true,'앞 단어만으로 다음 단어가 초성 0개에 뜬다');
    assert.ok(out.rankWithPrev>=0,'초성을 눌러도 후보에 남는다');
    assert.ok(out.rankNoPrev<0 || out.rankWithPrev<=out.rankNoPrev,
      '앞 단어가 있을 때의 순위가 없을 때보다 앞서거나 같다');
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});
