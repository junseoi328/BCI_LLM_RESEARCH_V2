from __future__ import annotations
import json, statistics, time
from collections import defaultdict
from pathlib import Path
from local_ft.common import normalize_text, read_jsonl
from local_ft.inference import LocalBCIGenerator
DEV=Path("training_v2/data/dev_semantic_v2.jsonl")
OUT=Path("eval_v2/reports/local_lora_generator_final.json")
def main()->int:
    rows=read_jsonl(DEV); gold=defaultdict(set)
    for r in rows:
        for t in r["candidates"]: gold[r["initials"]].add(t)
    gen=LocalBCIGenerator(); result=[]
    for i,ini in enumerate(sorted(gold),1):
        t0=time.perf_counter(); preds=gen.generate(ini,16); ms=(time.perf_counter()-t0)*1000
        g={normalize_text(x) for x in gold[ini]}; p={normalize_text(x) for x in preds}; hits=len(g&p)
        row={"initials":ini,"gold_recall":hits/len(g) if g else 0,"any_gold_hit":hits>0,"latency_ms":ms,"preds":preds}
        result.append(row); print(f"[{i:03d}/{len(gold):03d}] {ini} recall={row['gold_recall']:.3f} hit={row['any_gold_hit']} latency={ms:.0f}ms")
    s={"groups":len(result),"mean_gold_recall":statistics.mean(x["gold_recall"] for x in result),"any_gold_hit_rate":statistics.mean(float(x["any_gold_hit"]) for x in result),"mean_latency_ms":statistics.mean(x["latency_ms"] for x in result)}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({"summary":s,"rows":result},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(s,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
