/* 문장 통째 암기는 새 문장에 안 먹힌다. 그러면 '단어'와 '다음 단어'는
   얼마나 일반화되는가? 처음 보는 문장의 어절이 학습 색인에 있는 비율을 본다. */
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const rows=fs.readFileSync('/mnt/user-data/uploads/BCI_LLM_RESEARCH_V2/research/phrase_memory/approved_bci_phrase_bank_v2.jsonl','utf8')
    .split('\n').filter(Boolean).map(JSON.parse);
  let seed=7; const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
  const sh=[...rows].sort(()=>rnd()-0.5);
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
  const html=fs.readFileSync('/home/claude/v9.html','utf8');
  const page=await b.newPage();
  await page.route('**/*',r=>r.fulfill(new URL(r.request().url()).pathname==='/speller'?{contentType:'text/html',body:html}:{status:503,json:{}}));
  await page.goto('http://bci.test/speller');
  for(const [frac,lex] of [[0.25,0],[0.25,1],[0.5,0],[0.5,1],[0.75,0],[0.75,1]]){
    const cut=Math.floor(sh.length*frac);
    const r=await page.evaluate(({train,held,lex})=>{
      if(typeof SCORE!=='undefined') SCORE.lex=lex;
      try{localStorage.clear()}catch(e){}
      learn={word:{},next:{},phrase:{},ctx:{},day:today()};
      showView('speller'); el('autoPredict').checked=false; state.partner='family'; state.situation='general'; renderKeyboard();
      const SP=SEED_PHRASES.splice(0,SEED_PHRASES.length);
      const SW=SEED_WORDS.splice(0,SEED_WORDS.length);
      const SB=SEED_BIGRAMS.splice(0,SEED_BIGRAMS.length);
      for(const t of train) learnFromCommit(t.text);
      let words=0, known=0, wordHit=0, biHit=0, biTot=0;
      for(const t of held){
        const ws=t.text.split(/\s+/).filter(Boolean);
        let prev="";
        for(const w of ws){
          words++;
          if(learn.word[w]) known++;
          // 그 어절의 초성을 다 쳤을 때 단어 후보에 뜨는가
          state.initials=choseongOf(w); state.spelled={}; state.latest=[]; state.lastWord="";
          if(localWords(5).some(c=>c.text===w)) wordHit++;
          // 앞 단어를 알 때 다음 단어를 맞히는가
          if(prev){ biTot++; state.initials=""; state.lastWord=prev;
            if(nextWordGuesses(5).some(c=>c.text===w)) biHit++; }
          prev=w;
        }
      }
      SEED_PHRASES.push(...SP); SEED_WORDS.push(...SW); SEED_BIGRAMS.push(...SB);
      state.initials=''; state.lastWord=''; renderCandidatePanel();
      return {words,known,wordHit,biHit,biTot};
    },{train:sh.slice(0,cut),held:sh.slice(cut),lex});
    console.log(`말뭉치 ${lex?'켬':'끔'} · 학습 ${String(cut).padStart(3)}개 → 처음 보는 문장의 어절 ${r.words}개 중`
      +` 사전에 있음 ${(r.known/r.words*100).toFixed(1)}%`
      +` | 초성 다 쳤을 때 단어후보 적중 ${(r.wordHit/r.words*100).toFixed(1)}%`
      +` | 다음단어 예측 적중 ${(r.biHit/r.biTot*100).toFixed(1)}%`);
  }
  await b.close();
})();
