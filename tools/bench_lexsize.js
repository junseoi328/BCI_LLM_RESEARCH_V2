/* 넓은 말뭉치 층이 정말 8000 단어를 필요로 하는가.
   이 층은 gzip 기준 페이지의 절반(119KB 중 63KB)을 차지한다. 줄여도 성능이
   유지된다면 그만큼이 순수한 이득이다. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.initials,r.text,r.category]);
  const byCat={}; for(const r of rows)(byCat[r[2]]=byCat[r[2]]||[]).push(r);
  const mk=(s0)=>{let seed=s0;const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    const pool=[...rows].sort(()=>rnd()-0.5);const w=pool.map((_,i)=>1/(i+1)),t=w.reduce((a,c)=>a+c,0);
    const d=()=>{let r=rnd()*t;for(let i=0;i<pool.length;i++){r-=w[i];if(r<=0)return pool[i];}return pool[0];};
    return Array.from({length:300},()=>{const g=d();const sib=byCat[g[2]]||[g];
      return {text:g[1],cat:g[2],partner:sib[Math.floor(rnd()*sib.length)][1]};});};
  const html=fs.readFileSync('/home/claude/v11.html','utf8');
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');
  const run=async(label,nw,nb)=>{
    let K=0,B2=0,W=0,Z=0;
    for(const sd of [42,1337,20260921]){
      const r=await page.evaluate(({sess,nw,nb})=>{
        if(!window.__LW){ window.__LW=LEX_WORDS.slice(); window.__LB=LEX_BIGRAMS.slice(); }
        LEX_WORDS.length=0; LEX_WORDS.push(...window.__LW.slice(0,nw));
        LEX_BIGRAMS.length=0; LEX_BIGRAMS.push(...window.__LB.slice(0,nb));
        LEX_BUCKETS=null;
        try{localStorage.clear()}catch(e){}
        learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
        bgKey=null; showView('speller'); el('autoPredict').checked=false;
        state.partner='family'; renderKeyboard();
        const inv={}; for(const [s,cs] of Object.entries(SITU_CATS)) for(const c of cs) inv[c]=s;
        let keys=0,base=0,words=0,z=0;
        for(const t of sess){
          state.history=[{who:'partner',text:t.partner}]; state.committed=''; el('context').value='';
          state.situation=inv[t.cat]||'general';
          state.lastWord=''; state.lastWord2=''; markContextDirty();
          for(const w of String(t.text).trim().split(/\s+/)){
            const ini=choseongOf(w); if(!ini) continue;
            words++; base+=ini.length+1;
            state.initials=''; state.spelled={}; state.latest=[];
            let used=ini.length,hit=false;
            for(let k=0;k<=ini.length;k++){
              if(k>0) state.initials=ini.slice(0,k);
              renderCandidatePanel();
              if(slots.findIndex(s=>s.text===w)>=0){hit=true;used=k;break;}
            }
            keys+=used+1; if(hit&&used===0) z++;
            state.initials=''; state.spelled={}; learnFromCommit(w);
            state.committed=(state.committed?state.committed+' ':'')+w; markContextDirty();
          }
        }
        return {keys,base,words,z};
      },{sess:mk(sd),nw,nb});
      K+=r.keys;B2+=r.base;W+=r.words;Z+=r.z;
    }
    console.log(`${label.padEnd(30)} 절감 ${((1-K/B2)*100).toFixed(1)}% | 0초성 ${(Z/W*100).toFixed(1)}%`);
  };
  console.log('=== 말뭉치 층 크기 vs 성능 ===');
  for(const [nw,nb] of [[8000,2171],[6000,2171],[4000,2171],[2000,2171],[1000,2171],[0,2171],[8000,1000],[8000,0],[0,0]])
    await run(`단어 ${nw} · 바이그램 ${nb}`,nw,nb);
  await b.close();
})();
