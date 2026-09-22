/* 데이터를 더 모으면 정말 좋아지는가? — 늘리기 전에 재 본다.
   표현 사전 281개를 절반으로 갈라, 절반으로만 만든 색인으로 나머지 절반을
   맞혀 본다(held-out). 처음 보는 표현에 대한 실력이 곧 "데이터를 늘렸을 때
   기대할 수 있는 지점"이다. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse);
  let seed=7; const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
  const shuffled=[...rows].sort(()=>rnd()-0.5);
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
  const html=fs.readFileSync('/home/claude/v8.html','utf8');
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');

  const test=async(trainFrac,label)=>{
    const cut=Math.floor(shuffled.length*trainFrac);
    const train=shuffled.slice(0,cut), held=shuffled.slice(cut);
    const r=await page.evaluate(({train,held})=>{
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},phrase:{},ctx:{},day:today()};
      showView('speller'); el('autoPredict').checked=false;
      state.partner='family'; state.situation='general'; renderKeyboard();
      // 학습 분량만 색인에 넣는다 — 사전(SEED_*)은 비우고 학습 저장소로만 돌린다
      const SP=SEED_PHRASES.splice(0,SEED_PHRASES.length);
      const SW=SEED_WORDS.splice(0,SEED_WORDS.length);
      const SB=SEED_BIGRAMS.splice(0,SEED_BIGRAMS.length);
      for(const t of train) learnFromCommit(t.text);
      let solved=0,keys=0,base=0,n=0;
      for(const t of held){
        const ini=t.initials; if(!ini) continue;
        n++; base+=ini.length+1;
        state.initials=''; state.spelled={}; state.latest=[]; state.lastWord='';
        let used=0,hit=false;
        for(let k=0;k<=ini.length;k++){
          if(k>0){ state.initials=ini.slice(0,k); used=k; }
          renderCandidatePanel();
          if(slots.findIndex(s=>s.text===t.text)>=0){hit=true;break;}
        }
        if(hit){solved++;keys+=used+1;} else keys+=ini.length+1;
      }
      SEED_PHRASES.push(...SP); SEED_WORDS.push(...SW); SEED_BIGRAMS.push(...SB);
      state.initials=''; renderCandidatePanel();
      return {n,solved,keys,base,train:train.length};
    },{train,held});
    console.log(`${label.padEnd(30)} 학습 ${String(r.train).padStart(3)}개 -> 처음 보는 ${r.n}개: 적중 ${(r.solved/r.n*100).toFixed(1)}% | 절감 ${((1-r.keys/r.base)*100).toFixed(1)}%`);
    return r;
  };
  await test(0.25,'사전의 25% 만 알 때');
  await test(0.50,'사전의 50% 만 알 때');
  await test(0.75,'사전의 75% 만 알 때');
  await b.close();
})();
