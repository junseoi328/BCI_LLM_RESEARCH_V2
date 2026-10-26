/* 일반 대화(보류 문장)와 AAC 표현(Zipf 세션) 두 가지로 타건 절감을 잰다.
   usage: node bench_general.cjs <html> [label]
   - chat: 학습에 쓰지 않은 일상 대화 300문장. 문장 안에서 앞 단어를 이어 붙인다.
   - aac : 검수 표현 사전을 Zipf 로 뽑은 300문장 × 3시드, 학습 누적(실사용 흉내). */
const {chromium}=require('/opt/node-tools/node_modules/playwright');const fs=require('fs');
const [,,file,label='']=process.argv;
const chat=fs.readFileSync(process.env.CHAT_TEST||'/home/claude/data/chat_test.txt','utf8').split('\n').filter(Boolean);
const bank=fs.readFileSync('/home/claude/repo2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
  .split('\n').filter(Boolean).map(JSON.parse).map(r=>[r.text,r.category]);
(async()=>{
 const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'});
 const page=await b.newPage();
 const html=fs.readFileSync(file,'utf8');
 const dict=fs.existsSync('/home/claude/repo2/app/static/dict.txt')?fs.readFileSync('/home/claude/repo2/app/static/dict.txt','utf8'):'{}';
 await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
   if(p==='/speller')return r.fulfill({contentType:'text/html',body:html});
   if(p==='/speller/dict.txt')return r.fulfill({contentType:'text/plain',body:dict});
   return r.fulfill({status:503,json:{}});});
 await page.goto('http://bci.test/speller');
 await page.evaluate(()=>{showView('speller');return typeof loadDict==='function'?loadDict():null;}).catch(()=>{});
 console.error('dict entries', await page.evaluate(()=>typeof DICT!=='undefined'&&DICT?DICT.size:0));
 const run=(sents,mode,seed)=>page.evaluate(({sents,mode,seed})=>{
   try{localStorage.clear()}catch(e){}
   learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
   showView('speller');el('autoPredict').checked=false;state.partner='friend';state.situation='general';
   const inv={};for(const [s,cs] of Object.entries(SITU_CATS))for(const c of cs)inv[c]=s;
   let rnd=null; if(seed){let s0=seed;rnd=()=>((s0=(s0*1103515245+12345)&0x7fffffff)/0x7fffffff);}
   let list=sents;
   if(mode==='aac'){const pool=[...sents].sort(()=>rnd()-0.5);const w=pool.map((_,i)=>1/(i+1)),t=w.reduce((a,c)=>a+c,0);
     list=Array.from({length:300},()=>{let r=rnd()*t;for(let i=0;i<pool.length;i++){r-=w[i];if(r<=0)return pool[i];}return pool[0];});}
   let keys=0,base=0,words=0,z=0,cov=0;
   for(const item of list){
     const [text,cat]=Array.isArray(item)?item:[item,null];
     state.situation=cat?(inv[cat]||'general'):'general';state.lastWord='';state.lastWord2='';
     for(const raw of String(text).trim().split(/\s+/)){
       const w=raw.replace(/[.,!?~]+$/,''); const ini=choseongOf(w); if(!ini||!w)continue;
       words++;base+=ini.length+1;let used=ini.length,hit=false;
       for(let k=0;k<=ini.length;k++){
         state.initials=ini.slice(0,k);state.spelled={};state.latest=[];renderCandidatePanel();
         if(slots.some(s=>s.text===w)){hit=true;used=k;break;}
       }
       keys+=used+1;if(hit&&used===0)z++;if(hit)cov++;
       state.initials='';state.spelled={};
       if(mode==='aac') learnFromCommit(w); else {state.lastWord2=state.lastWord;state.lastWord=w;}
     }
   }
   return {ksr:1-keys/base,zero:z/words,cov:cov/words,words};
 },{sents,mode,seed});
 const c=await run(chat,'chat',0);
 let a={ksr:0,zero:0};for(const s of [42,1337,20260921]){const r=await run(bank,'aac',s);a.ksr+=r.ksr/3;a.zero+=r.zero/3;}
 const pct=x=>(x*100).toFixed(1)+'%';
 console.log(`${label.padEnd(18)} chat: 절감 ${pct(c.ksr)} · 0초성 ${pct(c.zero)} · 후보에 뜸 ${pct(c.cov)} (${c.words}어절) | aac: 절감 ${pct(a.ksr)} · 0초성 ${pct(a.zero)} | ${(html.length/1024|0)}KB`);
 await b.close();
})();
