const {chromium}=require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.initials,r.text,r.category]);
  const mk=(s0)=>{let seed=s0;const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    const pool=[...rows].sort(()=>rnd()-0.5);const w=pool.map((_,i)=>1/(i+1)),t=w.reduce((a,c)=>a+c,0);
    const d=()=>{let r=rnd()*t;for(let i=0;i<pool.length;i++){r-=w[i];if(r<=0)return pool[i];}return pool[0];};
    return Array.from({length:300},d);};
  const html=fs.readFileSync('/home/claude/v11.html','utf8');
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');
  const run=async(label,over)=>{
    let K=0,B=0,W=0,k0=0;
    for(const sd of [42,1337,20260921]){
      const r=await page.evaluate(({sess,over})=>{
        if(!window.__SCORE0) window.__SCORE0={...SCORE};
        Object.assign(SCORE,window.__SCORE0,over);   // 매 실행마다 기본값에서 다시 시작
        try{localStorage.clear()}catch(e){}
        learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
        bgKey=null;primedCats=new Set();mineCats=new Set();
        showView('speller');el('autoPredict').checked=false;state.partner='family';renderKeyboard();
        const inv={};for(const [s,cs] of Object.entries(SITU_CATS))for(const c of cs)inv[c]=s;
        let keys=0,base=0,words=0,z=0;
        for(const [,text,cat] of sess){
          state.situation=inv[cat]||'general';state.lastWord='';state.lastWord2='';
          for(const w of String(text).trim().split(/\s+/)){
            const ini=choseongOf(w);if(!ini)continue;
            words++;base+=ini.length+1;
            state.initials='';state.spelled={};state.latest=[];
            let used=ini.length,hit=false;
            for(let k=0;k<=ini.length;k++){
              if(k>0)state.initials=ini.slice(0,k);
              renderCandidatePanel();
              if(slots.findIndex(s=>s.text===w)>=0){hit=true;used=k;break;}
            }
            keys+=used+1; if(hit&&used===0)z++;
            state.initials='';state.spelled={};learnFromCommit(w);
          }
        }
        return {keys,base,words,z};
      },{sess:mk(sd),over});
      K+=r.keys;B+=r.base;W+=r.words;k0+=r.z;
    }
    console.log(`${label.padEnd(40)} 절감 ${((1-K/B)*100).toFixed(1)}% | 0초성 적중 ${(k0/W*100).toFixed(1)}%`);
  };
  await run('현재(트라이 + fallback)',{});
  await run('backoff(빈칸 채우기) 끔',{backoff:0});
  await run('트라이 끔',{triBase:0,triPer:0,bgTri:0,bgTriPer:0});
  await run('둘 다 끔',{backoff:0,triBase:0,triPer:0,bgTri:0,bgTriPer:0});
  await run('트라이 1400',{triBase:1400,triPer:120});
  await run('트라이 600',{triBase:600,triPer:60});
  await b.close();
})();
