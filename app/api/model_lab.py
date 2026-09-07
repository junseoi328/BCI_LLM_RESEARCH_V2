from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router=APIRouter(tags=["model-lab"])
D=Path("local_models/bci_generator_lora_final_v2")
E=Path("eval_v2/reports/local_lora_generator_final_v2_fixed.json")

@router.get("/model/status")
def model_status():
    out={"trained":(D/"metadata.json").exists(),"metadata":None,"history":[],"evaluation":None}
    if (D/"metadata.json").exists(): out["metadata"]=json.loads((D/"metadata.json").read_text(encoding="utf-8"))
    if (D/"training_history.json").exists(): out["history"]=json.loads((D/"training_history.json").read_text(encoding="utf-8"))
    if E.exists(): out["evaluation"]=json.loads(E.read_text(encoding="utf-8")).get("summary")
    return out

@router.get("/model-lab",response_class=HTMLResponse)
def model_lab():
    return HTMLResponse("""
<!doctype html><html lang="ko"><meta charset="utf-8"><title>BCI Model Lab</title>
<style>
body{font-family:Arial;max-width:1100px;margin:35px auto;background:#111;color:#eee;padding:0 20px}
.card{border:1px solid #444;border-radius:14px;padding:18px;margin:14px 0;background:#1a1a1a}
input,select,textarea,button{font:inherit;padding:10px;margin:5px;background:#222;color:#eee;border:1px solid #555;border-radius:8px}
pre{background:#0d0d0d;padding:14px;border-radius:8px;white-space:pre-wrap}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #444}
.metric{display:inline-block;min-width:180px;padding:10px;margin:5px;border:1px solid #555;border-radius:9px}
</style>
<h1>BCI Language Model Lab</h1>
<div class="card"><h2>Fine-tuned model</h2><div id="metrics"></div><pre id="meta"></pre></div>
<div class="card"><h2>Training history</h2><table><thead><tr><th>epoch</th><th>step</th><th>train loss</th><th>eval loss</th><th>sec</th></tr></thead><tbody id="hist"></tbody></table></div>
<div class="card"><h2>BCI /predict</h2>
<input id="ini" value="ㅁㅈ"><select id="partner"><option>family</option><option>caregiver</option><option>medical_staff</option><option>friend</option><option>other</option></select>
<input id="sit" value="home"><br><textarea id="ctx" rows="3" style="width:95%">목이 말라서 물을 마시고 싶다</textarea><br>
<button onclick="go()">Predict</button><pre id="result"></pre></div>
<script>
async function load(){
 let r=await fetch('/model/status'),d=await r.json(),e=d.evaluation||{};
 document.getElementById('meta').textContent=JSON.stringify(d.metadata,null,2);
 document.getElementById('metrics').innerHTML=
 `<span class=metric>trained<br><b>${d.trained}</b></span>`+
 `<span class=metric>recall<br><b>${e.mean_gold_recall??'-'}</b></span>`+
 `<span class=metric>any-hit<br><b>${e.any_gold_hit_rate??'-'}</b></span>`+
 `<span class=metric>latency ms<br><b>${e.mean_latency_ms??'-'}</b></span>`;
 let h=document.getElementById('hist'); h.innerHTML='';
 for(let x of d.history||[]) h.innerHTML+=`<tr><td>${x.epoch}</td><td>${x.global_step}</td><td>${x.train_loss.toFixed(4)}</td><td>${x.eval_loss.toFixed(4)}</td><td>${x.elapsed_sec.toFixed(1)}</td></tr>`;
}
async function go(){
 let body={input_mode:'initials',bci_input:document.getElementById('ini').value,partner:document.getElementById('partner').value,situation:document.getElementById('sit').value,current_sentence:'',recent_context:[document.getElementById('ctx').value],top_k:3};
 let r=await fetch('/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2);
}
load();
</script></html>
""")
