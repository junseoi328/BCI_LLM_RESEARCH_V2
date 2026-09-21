/* 현실적인 사용을 흉내 낸 측정.
   앞 측정은 서로 다른 표현 281개를 한 번씩 훑는 방식이라, 개인화에는 최악의
   조건이었다(방금 배운 것이 다음 목표와 아무 상관이 없다). 실제 사용자는
   같은 말을 자주 되풀이한다 — 소수의 표현이 대부분을 차지하는 분포다.
   그래서 Zipf 분포로 표현을 뽑아 한 세션을 흉내 내고, 문장 하나를 완성하는 데
   든 키 누름 수를 센다. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.initials,r.text,r.category]);
  // 재현 가능한 의사난수
  const makeSession=(s0)=>{
    let seed=s0; const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    const pool=[...rows].sort(()=>rnd()-0.5);
    const weights=pool.map((_,i)=>1/(i+1));
    const total=weights.reduce((a,c)=>a+c,0);
    const draw=()=>{ let r=rnd()*total; for(let i=0;i<pool.length;i++){ r-=weights[i]; if(r<=0) return pool[i]; } return pool[0]; };
    return Array.from({length:400},draw);
  };
  let session=makeSession(42);

  const run=async(file,label,over)=>{
    const page=await b.newPage();
    const html=fs.readFileSync(file,'utf8');
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
    await page.goto('http://bci.test/speller');
    const res=await page.evaluate(({sess,over})=>{
      if(typeof SCORE!=='undefined'&&over) Object.assign(SCORE,over);
      try{localStorage.clear()}catch(e){}
      if(typeof learn!=='undefined') learn={word:{},next:{},phrase:{},ctx:{},day:today()};
      showView('speller'); el('autoPredict').checked=false; state.partner='family'; renderKeyboard();
      const inv={}; for(const [s,cs] of Object.entries(SITU_CATS)) for(const c of cs) inv[c]=s;
      let keys=0, base=0, solved=0, first=0;
      for(const [ini,text,cat] of sess){
        if(!ini) continue;
        base+=ini.length+1;
        state.situation=inv[cat]||'general'; state.initials=''; state.spelled={}; state.latest=[];
        let used=0,hit=false,rank=-1;
        for(let k=0;k<=ini.length;k++){
          if(k>0){ state.initials=ini.slice(0,k); used=k; }
          renderCandidatePanel();
          const i=slots.findIndex(s=>s.text===text);
          if(i>=0){hit=true;rank=i;break;}
        }
        if(hit){ solved++; keys+=used+1; if(rank===0) first++; } else keys+=ini.length+1;
        if(typeof learnFromCommit==='function') learnFromCommit(text);
        else { recordHabitual(text); for(const w of text.split(/\s+/)) recordWordFreq(w); }
        state.lastWord='';
      }
      state.initials=''; renderCandidatePanel();
      return {n:sess.length,solved,keys,base,first};
    },{sess:session,over});
    console.log(`${label.padEnd(30)} 절감 ${((1-res.keys/res.base)*100).toFixed(1)}% | 1번 자리 ${(res.first/res.n*100).toFixed(1)}% | 키 ${res.keys}/${res.base}`);
    await page.close();
    return res;
  };
  const BASE={exact:1000,prefix:300,learnBase:300,learnPer:40,learnCap:12,cat:180,freq:4,guessPenalty:0};
  const configs=[['학습 끔',{learnBase:0,learnPer:0,cat:180}],
                 ['learn120 cat180',{learnBase:120,learnPer:20,cat:180}],
                 ['learn300 cat400',{learnBase:300,learnPer:40,cat:400}],
                 ['learn300 cat600',{learnBase:300,learnPer:40,cat:600}],
                 ['learn200 cat500',{learnBase:200,learnPer:30,cat:500}]];
  const agg={};
  for(const sd of [42,1337,20260921]){
    session=makeSession(sd);
    const r0=await run('/home/claude/v7.html',`seed${sd} 이전 v1.1`,null);
    agg['이전 v1.1']=(agg['이전 v1.1']||0)+(1-r0.keys/r0.base)*100;
    for(const [lbl,over] of configs){
      const r=await run('/home/claude/v8.html',`seed${sd} ${lbl}`,{...BASE,...over});
      agg[lbl]=(agg[lbl]||0)+(1-r.keys/r.base)*100;
    }
  }
  console.log('\n=== 세 세션 평균 절감률 ===');
  for(const [k,v] of Object.entries(agg)) console.log(`${k.padEnd(20)} ${(v/3).toFixed(1)}%`);
  await b.close();
})();
