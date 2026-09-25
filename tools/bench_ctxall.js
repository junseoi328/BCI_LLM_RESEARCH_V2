/* 문맥의 모든 형태가 각각 얼마나 기여하는가.
   앞선 측정들은 사용자 발화만 있고 대화 상대가 없었다. 여기서는 같은 카테고리의
   다른 표현을 상대 발화로 먼저 넣어 실제 대화를 흉내 낸다 — 주제 연속성이 생기고,
   그래야 "상대 말에서 상황 읽기"가 공정하게 측정된다. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.initials,r.text,r.category]);
  const byCat={}; for(const r of rows) (byCat[r[2]]=byCat[r[2]]||[]).push(r);
  const mk=(s0)=>{ let seed=s0; const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    const pool=[...rows].sort(()=>rnd()-0.5);
    const w=pool.map((_,i)=>1/(i+1)), t=w.reduce((a,c)=>a+c,0);
    const draw=()=>{ let r=rnd()*t; for(let i=0;i<pool.length;i++){ r-=w[i]; if(r<=0) return pool[i]; } return pool[0]; };
    return Array.from({length:300},()=>{
      const tgt=draw(); const sib=byCat[tgt[2]]||[tgt];
      return {ini:tgt[0], text:tgt[1], cat:tgt[2], partner:sib[Math.floor(rnd()*sib.length)][1]};
    });
  };
  const html=fs.readFileSync('/home/claude/v11.html','utf8');
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');

  const run=async(label,use,wOver)=>{
    let K=0,B=0,W=0,Z=0;
    for(const sd of [42,1337,20260921]){
      const r=await page.evaluate(({sess,use,wOver})=>{
        if(!window.__W0) window.__W0=JSON.parse(JSON.stringify(CTX_W));
        Object.assign(CTX_W, JSON.parse(JSON.stringify(window.__W0)), wOver||{});
        try{localStorage.clear()}catch(e){}
        learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
        bgKey=null; showView('speller'); el('autoPredict').checked=false;
        state.partner='family'; renderKeyboard();
        const inv={}; for(const [s,cs] of Object.entries(SITU_CATS)) for(const c of cs) inv[c]=s;
        let keys=0,base=0,words=0,z=0;
        for(const t of sess){
          state.history=[]; state.committed=''; el('context').value='';
          state.situation = use.situ ? (inv[t.cat]||'general') : 'general';
          if(use.partner) state.history.push({who:'partner',text:t.partner});
          if(use.memo)    el('context').value=t.partner;      // 보호자가 상황을 적어 둔 경우
          state.lastWord=''; state.lastWord2=''; markContextDirty();
          for(const w of String(t.text).trim().split(/\s+/)){
            const ini=choseongOf(w); if(!ini) continue;
            words++; base+=ini.length+1;
            state.initials=''; state.spelled={}; state.latest=[];
            let used=ini.length, hit=false;
            for(let k=0;k<=ini.length;k++){
              if(k>0) state.initials=ini.slice(0,k);
              renderCandidatePanel();
              if(slots.findIndex(s=>s.text===w)>=0){ hit=true; used=k; break; }
            }
            keys+=used+1; if(hit&&used===0) z++;
            state.initials=''; state.spelled={};
            learnFromCommit(w);
            if(use.buffer){ state.committed=(state.committed?state.committed+' ':'')+w; markContextDirty(); }
          }
        }
        return {keys,base,words,z};
      },{sess:mk(sd),use,wOver});
      K+=r.keys;B+=r.base;W+=r.words;Z+=r.z;
    }
    console.log(`${label.padEnd(36)} 절감 ${((1-K/B)*100).toFixed(1)}% | 0초성 적중 ${(Z/W*100).toFixed(1)}%`);
    return (1-K/B)*100;
  };

  const NONE={situ:0,partner:0,memo:0,buffer:0};
  console.log('=== 문맥 신호별 기여 (3세션 합산, 상대 발화 있는 대화) ===');
  await run('0. 아무 문맥 없음',            NONE);
  await run('1. 상황 선택만',               {...NONE,situ:1});
  await run('2. 상대 말만',                 {...NONE,partner:1});
  await run('3. 상황 메모만',               {...NONE,memo:1});
  await run('4. 문장 버퍼만',               {...NONE,buffer:1});
  await run('5. 전부 (가중치)',             {situ:1,partner:1,memo:1,buffer:1});
  await run('6. 전부 (가중치 없이 전부 1.0)',{situ:1,partner:1,memo:1,buffer:1},
            {situation:1,memo:1,buffer:1,mine:1,partner:[1,1,1]});
  await page.evaluate(()=>SCORE.echo=0);
  await run('7. 전부, 단 상대 단어 에코 끔',{situ:1,partner:1,memo:1,buffer:1});
  await b.close();
})();
