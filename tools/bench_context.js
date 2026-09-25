/* 상대·상황 선택이 실제로 얼마나 기여하는가.
   온보딩에서 두 번 고르게 할 값어치가 있는지, 아니면 대화에서 읽어내도
   되는지를 가른다. 같은 세션·같은 시드로 네 조건만 바꿔 비교한다. */
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
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');

  const run=async(label,mode)=>{
    const acc=[];
    for(const sd of [42,1337,20260921]){
      acc.push(await page.evaluate(({sess,mode,gc})=>{
        try{localStorage.clear()}catch(e){}
        learn={word:{},next:{},phrase:{},ctx:{},day:today()};
        bgKey=null; primedCats=new Set(); mineCats=new Set();
        SCORE.guessCat=Number(gc||0);
        showView('speller'); el('autoPredict').checked=false;
        state.partner='family'; renderKeyboard();
        const inv={}; for(const [s,cs] of Object.entries(SITU_CATS)) for(const c of cs) inv[c]=s;
        let keys=0, base=0, words=0, k0=0;
        let prevText='';
        for(const [,text,cat] of sess){
          // mode: 'given'  = 사용자가 상황을 정확히 고름
          //       'general'= 아무도 안 고름(항상 일반 대화)
          //       'infer'  = 고르지 않고, 직전 대화 한 줄에서 카테고리를 읽음
          const SITU=Object.keys(SITU_CATS);
          if(mode==='given')      state.situation=inv[cat]||'general';
          else if(mode==='wrong'){ // 사용자가 엉뚱한 상황을 골라 두고 안 바꾼 경우
            state.situation='meal'; }
          else if(mode==='random'){ state.situation=SITU[words%SITU.length]; }
          else                    state.situation='general';
          if(mode==='infer'){ primedCats = prevText ? readCats(prevText,2) : new Set(); }
          else if(mode!=='given'){ primedCats=new Set(); }
          if(mode!=='mine') mineCats=new Set();
          state.lastWord='';
          for(const w of String(text).trim().split(/\s+/)){
            const ini=choseongOf(w); if(!ini) continue;
            words++; base+=ini.length+1;
            state.initials=''; state.spelled={}; state.latest=[];
            let used=ini.length, hit=false;
            for(let k=0;k<=ini.length;k++){
              if(k>0) state.initials=ini.slice(0,k);
              renderCandidatePanel();
              if(slots.findIndex(s=>s.text===w)>=0){ hit=true; used=k; break; }
            }
            keys+=used+1; if(hit&&used===0) k0++;
            state.initials=''; state.spelled={};
            learnFromCommit(w);
          }
          prevText=text;
        }
        return {keys,base,words,k0};
      },{sess:makeSession(sd),mode,gc:process.env.GC}));
    }
    const s={}; for(const k of ['keys','base','words','k0']) s[k]=acc.reduce((a,r)=>a+r[k],0);
    console.log(`${label.padEnd(38)} 절감 ${((1-s.keys/s.base)*100).toFixed(1)}%  |  초성 0개로 맞힌 단어 ${(s.k0/s.words*100).toFixed(1)}%`);
  };

  console.log('=== 상황 정보를 어디서 얻을 것인가 (3세션 합산) ===');
  await run('A. 사용자가 상황을 정확히 고름','given');
  await run('B. 아무도 안 고름 (항상 일반 대화)','general');
  await run('C. 안 고르고 직전 대화에서 읽음','infer');
  await run("D. 한 번 잘못 골라 두고 안 바꿈 ('식사' 고정)",'wrong');
  await run('E. 매번 무작위 상황','random');
  await b.close();
})();
