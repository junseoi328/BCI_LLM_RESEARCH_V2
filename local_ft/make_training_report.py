from __future__ import annotations
import json
from pathlib import Path
D=Path("local_models/bci_generator_lora_final")
OUT=D/"training_report.html"
def main()->int:
    h=D/"training_history.json"; m=D/"metadata.json"
    if not h.exists() or not m.exists(): print("training result 없음"); return 2
    hist=json.loads(h.read_text(encoding="utf-8")); meta=json.loads(m.read_text(encoding="utf-8"))
    rows="".join(f"<tr><td>{x['epoch']}</td><td>{x['global_step']}</td><td>{x['train_loss']:.4f}</td><td>{x['eval_loss']:.4f}</td><td>{x['elapsed_sec']:.1f}</td></tr>" for x in hist)
    html=f"""<!doctype html><html><meta charset='utf-8'><title>BCI Training</title><style>body{{font-family:Arial;max-width:900px;margin:40px auto}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px}}pre{{background:#eee;padding:15px}}</style><h1>BCI Local LoRA Training</h1><pre>{json.dumps(meta,ensure_ascii=False,indent=2)}</pre><table><tr><th>Epoch</th><th>Step</th><th>Train loss</th><th>Eval loss</th><th>sec</th></tr>{rows}</table></html>"""
    OUT.write_text(html,encoding="utf-8"); print("REPORT:",OUT); return 0
if __name__=="__main__": raise SystemExit(main())
