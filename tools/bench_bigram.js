/* 앞 단어 가산점 측정.
   기존 bench_ksr 는 문장마다 state.lastWord 를 비워서 바이그램 경로를 한 번도
   타지 않았다. 여기서는 문장을 어절 단위로 입력하고 lastWord 를 이어 붙인다 —
   "물"을 고른 뒤 "좀"을 찾을 때 앞 단어가 실제로 도움이 되는지가 이 측정의 전부. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.initials,r.text,r.category]);
  const makeSession=(s0)=>{
    let seed=s0; const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    const pool=[...rows].sort(()=>rnd()-0.5);
    const w=pool.map((_,i)=>1/(i+1)), total=w.reduce((a,c)=>a+c,0);
    const draw=()=>{ let r=rnd()*total; for(let i=0;i<pool.length;i++){ r-=w[i]; if(r<=0) return pool[i]; } return pool[0]; };
    return Array.from({length:300},draw);
  };

  const html=fs.readFileSync('/home/claude/v11.html','utf8');
  const run=async(label,over)=>{
    const page=await b.newPage();
    await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
    await page.goto('http://bci.test/speller');
    const out=[];
    for(const sd of [42,1337,20260921]){
      const res=await page.evaluate(({sess,over})=>{
        Object.assign(SCORE,over);
        try{localStorage.clear()}catch(e){}
        learn={word:{},next:{},phrase:{},ctx:{},day:today()};
        bgKey=null; primedCats=new Set(); mineCats=new Set();
        showView('speller'); el('autoPredict').checked=false;
        state.partner='family'; renderKeyboard();
        const inv={}; for(const [s,cs] of Object.entries(SITU_CATS)) for(const c of cs) inv[c]=s;
        let keys=0, base=0, words=0, hits=0, rank1=0, hardN=0, hardKeys=0, hardRank=0, hardHit=0;
        for(const [,text,cat] of sess){
          state.situation=inv[cat]||'general';
          state.lastWord='';                       // 새 문장은 내 차례의 첫 어절부터
          for(const w of String(text).trim().split(/\s+/)){
            const ini=choseongOf(w); if(!ini) continue;
            words++; base+=ini.length+1;
            state.initials=''; state.spelled={}; state.latest=[];
            let used=ini.length, hit=false, rank=-1;
            for(let k=0;k<=ini.length;k++){
              if(k>0) state.initials=ini.slice(0,k);
              renderCandidatePanel();
              const i=slots.findIndex(s=>s.text===w);
              if(i>=0){ hit=true; rank=i; used=k; break; }
            }
            keys+=used+1;
            if(hit){ hits++; if(rank===0) rank1++; }
            // k=0(초성 0개)에서 이미 맞힌 건 예전부터 되던 경로다. 앞 단어
            // 가산점이 실제로 작용하는 구간은 초성을 눌러야 했던 단어들뿐이다.
            if(!(hit&&rank>=0&&used===0)){ hardN++; hardKeys+=used; if(hit){hardHit++; hardRank+=rank;} }
            state.initials=''; state.spelled={};
            learnFromCommit(w);                     // = 그 단어를 고른 것
          }
        }
        return {keys,base,words,hits,rank1,hardN,hardKeys,hardRank,hardHit};
      },{sess:makeSession(sd),over});
      out.push(res);
    }
    const K=['keys','base','words','hits','rank1','hardN','hardKeys','hardRank','hardHit'];
    const sum={}; for(const k of K) sum[k]=out.reduce((a,r)=>a+r[k],0);
    console.log(`${label.padEnd(30)} 절감 ${((1-sum.keys/sum.base)*100).toFixed(1)}% | 적중 ${(sum.hits/sum.words*100).toFixed(1)}% | 초성 필요했던 ${sum.hardN}개: 평균 초성 ${(sum.hardKeys/sum.hardN).toFixed(2)} · 평균 순위 ${(sum.hardRank/Math.max(1,sum.hardHit)).toFixed(2)} · 적중 ${(sum.hardHit/sum.hardN*100).toFixed(1)}%`);
    await page.close();
    return (1-sum.keys/sum.base)*100;
  };

  console.log('=== 앞 단어 가산점 (3세션 합산, 어절 단위 입력) ===');
  for(const [lbl,over] of [
    ['끔  bgMine 0',              {bgMine:0,bgMinePer:0,bgSeed:0,bgLex:0}],
    ['내 기록만 300',             {bgMine:300,bgMinePer:30,bgSeed:0,bgLex:0}],
    ['내 기록만 600',             {bgMine:600,bgMinePer:60,bgSeed:0,bgLex:0}],
    ['내 기록만 1200',            {bgMine:1200,bgMinePer:120,bgSeed:0,bgLex:0}],
    ['600 + 사전 40',             {bgMine:600,bgMinePer:60,bgSeed:40,bgLex:0}],
    ['600 + 사전 40 + 말뭉치 8',  {bgMine:600,bgMinePer:60,bgSeed:40,bgLex:8}],
    ['600 + 사전 120 + 말뭉치 20',{bgMine:600,bgMinePer:60,bgSeed:120,bgLex:20}],
    ['1200 + 사전 120 + 말뭉치 20',{bgMine:1200,bgMinePer:120,bgSeed:120,bgLex:20}],
  ]) await run(lbl,over);
  await b.close();
})();
