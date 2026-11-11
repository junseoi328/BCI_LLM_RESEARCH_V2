/* '원하는 말 없음' 루프 벤치: 보류 문장(chat_test)의 초성을 다 친 뒤, 후보에 없으면 글자 하나를 채우고 다시 찾는다.
   전략별로 몇 글자를 채워야 문장이 후보 7칸에 뜨는지. usage: CHAT_TEST=… node tools/bench_none.cjs <html> */
const {chromium}=require('playwright');const fs=require('fs');
const [,,file]=process.argv;
const sents=fs.readFileSync(process.env.CHAT_TEST||'data/chat_test.txt','utf8').split('\n').map(s=>s.trim()).filter(Boolean).slice(0,+(process.env.N||150));
(async()=>{
 const b=await chromium.launch();const page=await b.newPage();
 const html=fs.readFileSync(file,'utf8'), dict=fs.readFileSync(__dirname+'/../app/static/dict.txt','utf8');
 await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
   if(p==='/speller')return r.fulfill({contentType:'text/html',body:html});
   if(p==='/speller/dict.txt')return r.fulfill({contentType:'text/plain',body:dict});
   return r.fulfill({status:503,json:{}});});
 await page.goto('http://bci.test/speller');
 await page.evaluate(k=>{ if(typeof setKbLayout==='function') setKbLayout(k); }, process.env.KB||'k40');  // 기준은 40키(이력과 비교), KB=fig 로 환자 실험용 자판
 await page.evaluate(()=>{showView('speller');return loadDict();});
 for(const strat of ['entropy','first','last']){
  const r=await page.evaluate(({sents,strat})=>{
   const norm=t=>String(t).replace(/[^가-힣]/g,'');
   let n=0,found0=0,fills=0,solved=0,within2=0;
   for(const s of sents){
     const sy=[...norm(s)]; if(sy.length<2||sy.length>20) continue; n++;
     try{localStorage.clear()}catch(e){}
     learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
     state.partner='family';state.situation='general';el('autoPredict').checked=false;
     state.history=[];state.committed='';state.lastWord='';state.lastWord2='';state.latest=[];state.breaks=[];
     state.initials=choseongOf(sy.join(''));state.spelled={};markContextDirty();
     let k=0;
     for(;;){
       renderCandidatePanel();
       if(slots.some(x=>x&&norm(x.text)===sy.join(''))) break;
       const open=[...sy.keys()].filter(i=>!state.spelled[i]); if(!open.length){k=-1;break;}
       const i= strat==='entropy'? bestSpellTarget() : strat==='first'? open[0] : open[open.length-1];
       state.spelled[i]=sy[i]; k++;
     }
     if(k===0) found0++; else if(k>0){ fills+=k; solved++; if(k<=2) within2++; }
   }
   return {n,found0,solved,avgFills:(fills/Math.max(1,solved)).toFixed(2),within2};
  },{sents,strat});
  console.log(strat.padEnd(8), JSON.stringify(r));
 }
 await b.close();})();
