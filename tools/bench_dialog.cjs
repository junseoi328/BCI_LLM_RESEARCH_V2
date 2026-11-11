/* 대화 문맥 벤치: 앞선 대화(상대·나)를 history에 넣고 마지막 내 말을 단어마다 몇 타로 고르는지.
   usage: node tools/bench_dialog.cjs <html> [label]. 손으로 쓴 32대화(tools/ctx_dialogs.json) — 작고 저자 편향이 있다. */
const {chromium}=require('playwright');const fs=require('fs');
const [,,file,label='']=process.argv;
const dialogs=JSON.parse(fs.readFileSync(__dirname+'/ctx_dialogs.json','utf8'));
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
 if(process.env.DBG) await page.evaluate(()=>window.__DBG=[]);
 const r=await page.evaluate(dialogs=>{
   let keys=0,base=0,first=0,n=0,top1=0;
   for(const d of dialogs){
     try{localStorage.clear()}catch(e){}
     learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
     state.partner='family';state.situation='general';el('autoPredict').checked=false;el('context').value='';
     const target=d[d.length-1][1];
     state.history=d.slice(0,-1).map(([w,t])=>({who:w==='me'?'me':'partner',text:t,done:true}));
     state.committed='';state.lastWord='';state.lastWord2='';markContextDirty();
     for(const w of target.split(/\s+/)){
       const ini=choseongOf(w); n++; base+=ini.length+1;
       let used=ini.length;
       for(let k=0;k<=ini.length;k++){ state.initials=ini.slice(0,k); state.spelled={}; state.latest=[];
         renderCandidatePanel(); const at=slots.findIndex(s=>s.text===w); if(at>=0){used=k;if(at===0)top1++;break;} }
       keys+=used+1; if(used<ini.length) first++;
       if(window.__DBG && used>=1){ state.initials=ini.slice(0,1); renderCandidatePanel(); window.__DBG.push(`${w}(${used}/${ini.length}) @${ini[0]}: ${slots.slice(0,4).map(s=>s.text).join(',')} | ctx=${d.slice(0,-1).map(x=>x[1]).join('/')}`.slice(0,150)); state.initials=''; }
       state.initials='';state.committed=(state.committed?state.committed+' ':'')+w;
       state.lastWord2=state.lastWord;state.lastWord=w;markContextDirty();
     }
   }
   return {keys,base,first,n,top1};
 },dialogs);
 console.log(`${label.padEnd(10)} dialog: 절감 ${((1-r.keys/r.base)*100).toFixed(1)}% · 초성 다 치기 전 적중 ${(r.first/r.n*100).toFixed(1)}% · 1번 자리 ${(r.top1/r.n*100).toFixed(1)}% (${r.n}어절)`);
 if(process.env.DBG) console.log((await page.evaluate(()=>window.__DBG)).join('\n'));
 await b.close();})();
