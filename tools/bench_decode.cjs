/* 띄어쓰기 없이 친 문장 초성 -> 문장 복원 정확도. node bench_decode.cjs <html> [label] */
const {chromium}=require('/opt/node-tools/node_modules/playwright');const fs=require('fs');
const [,,file,label='']=process.argv;
const chat=fs.readFileSync(process.env.CHAT_TEST||'/home/claude/data/chat_test.txt','utf8').split('\n').filter(Boolean);
const bank=fs.readFileSync('/home/claude/repo2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8').split('\n').filter(Boolean).map(l=>JSON.parse(l).text);
const extra=process.env.EXTRA_TEST?fs.readFileSync(process.env.EXTRA_TEST,'utf8').split('\n').filter(Boolean):[];
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'});
const page=await b.newPage();const html=fs.readFileSync(file,'utf8');const dict=fs.readFileSync(process.env.DICT_FILE||'/home/claude/repo2/app/static/dict.txt','utf8');
await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;
 if(p==='/speller')return r.fulfill({contentType:'text/html',body:html});
 if(p==='/speller/dict.txt')return r.fulfill({contentType:'text/plain',body:dict});
 return r.fulfill({status:503,json:{}});});
await page.goto('http://bci.test/speller');
await page.evaluate(async()=>{showView('speller');if(typeof loadDict==='function')await loadDict();});
const run=list=>page.evaluate(list=>{
  try{localStorage.clear()}catch(e){}
  learn={word:{},next:{},next2:{},phrase:{},ctx:{},day:today()};
  state.partner='family';state.situation='general';el('autoPredict').checked=false;
  const norm=t=>t.replace(/[.,!?~]/g,'').trim().replace(/\s+/g,' ');
  let top1=0,top3=0,shown=0,ms=0,keys=0,base=0;
  for(const raw of list){
    const t=norm(raw); const ini=choseongOf(t); if(ini.length<2) continue;
    state.lastWord='';state.lastWord2='';state.initials=ini;state.spelled={};state.latest=[];
    const s=performance.now(); renderCandidatePanel(); ms+=performance.now()-s;
    const sents=slots.filter(x=>x.kind==='sent').map(x=>norm(x.text));
    const dec=(typeof decodeSentences==='function'?decodeSentences(ini,3):[]).map(norm);
    if(dec[0]===t) top1++; if(dec.includes(t)) top3++; if(sents.includes(t)) shown++;
    // 문장 단위 절감: 초성을 하나씩 칠 때 몇 번째에 문장 칸에 뜨나 (끝까지 안 뜨면 전부 친 것으로)
    let used=ini.length;
    for(let k=1;k<=ini.length;k++){ state.initials=ini.slice(0,k); renderCandidatePanel();
      if(slots.some(x=>x.kind==='sent'&&norm(x.text)===t)){used=k;break;} }
    keys+=used+1; base+=ini.length+1;
  }
  return {n:list.length,top1:top1/list.length,top3:top3/list.length,shown:shown/list.length,ms:ms/list.length,ksr:1-keys/base};
},list);
const pct=x=>(x*100).toFixed(1)+'%';
for(const [name,list] of [['AAC 표현',bank],['일상 대화',chat],...(extra.length?[['추가',extra]]:[])]){
  const r=await run(list); console.log(`${label.padEnd(14)} ${name}(${r.n}): 1위 ${pct(r.top1)} · 3위 안 ${pct(r.top3)} · 문장 칸에 뜸 ${pct(r.shown)} · 문장 절감 ${pct(r.ksr)} · ${r.ms.toFixed(1)}ms`);
}
await b.close();})();
