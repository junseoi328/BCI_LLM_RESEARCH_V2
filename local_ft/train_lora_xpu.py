from __future__ import annotations
import json, os, random, time
from dataclasses import dataclass
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from peft import LoraConfig, get_peft_model
from transformers import AutoTokenizer, AutoModelForCausalLM
from local_ft.common import read_jsonl

TRAIN=Path(os.getenv("LOCAL_TRAIN_FILE","training_v2/data/openai/train_sft_v2.jsonl"))
DEV=Path(os.getenv("LOCAL_DEV_FILE","training_v2/data/openai/dev_sft_v2.jsonl"))
BASE=os.getenv("LOCAL_BASE_MODEL","Qwen/Qwen2.5-0.5B-Instruct")
OUT=Path(os.getenv("LOCAL_OUTPUT_DIR","local_models/bci_generator_lora_final"))
MAXLEN=int(os.getenv("LOCAL_MAX_LENGTH","512"))
EPOCHS=int(os.getenv("LOCAL_EPOCHS","3"))
LR=float(os.getenv("LOCAL_LR","2e-4"))
ACCUM=int(os.getenv("LOCAL_GRAD_ACCUM","8"))
SEED=int(os.getenv("LOCAL_SEED","20260902"))

class SFTDataset(Dataset):
    def __init__(self,rows,tok):
        self.items=[]
        for row in rows:
            m=row.get("messages") or []
            if len(m)<3: continue
            prompt=tok.apply_chat_template(m[:-1],tokenize=False,add_generation_prompt=True)
            answer=str(m[-1]["content"])
            full=prompt+answer+(tok.eos_token or "")
            pids=tok(prompt,add_special_tokens=False,truncation=True,max_length=MAXLEN)["input_ids"]
            enc=tok(full,add_special_tokens=False,truncation=True,max_length=MAXLEN)
            labels=list(enc["input_ids"]); n=min(len(pids),len(labels)); labels[:n]=[-100]*n
            if all(x==-100 for x in labels): continue
            self.items.append({"input_ids":enc["input_ids"],"attention_mask":enc["attention_mask"],"labels":labels})
    def __len__(self): return len(self.items)
    def __getitem__(self,i): return self.items[i]

@dataclass
class Collate:
    pad:int
    def __call__(self,b):
        n=max(len(x["input_ids"]) for x in b)
        ids=[]; masks=[]; labels=[]
        for x in b:
            p=n-len(x["input_ids"])
            ids.append(x["input_ids"]+[self.pad]*p)
            masks.append(x["attention_mask"]+[0]*p)
            labels.append(x["labels"]+[-100]*p)
        return {"input_ids":torch.tensor(ids),"attention_mask":torch.tensor(masks),"labels":torch.tensor(labels)}

def mv(batch): return {k:v.to("xpu") for k,v in batch.items()}

@torch.no_grad()
def eval_loss(model,loader):
    model.eval(); losses=[]
    for i,b in enumerate(loader):
        if i>=100: break
        losses.append(float(model(**mv(b)).loss.detach().cpu()))
    model.train()
    return sum(losses)/len(losses) if losses else float("nan")

def main()->int:
    random.seed(SEED); torch.manual_seed(SEED)
    if not (hasattr(torch,"xpu") and torch.xpu.is_available()):
        print("ERROR: XPU unavailable"); return 2
    dtype=torch.bfloat16 if torch.xpu.is_bf16_supported() else torch.float32
    print("BASE=",BASE); print("XPU=",torch.xpu.get_device_name(0)); print("dtype=",dtype)
    tok=AutoTokenizer.from_pretrained(BASE,trust_remote_code=True,use_fast=True)
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(BASE,torch_dtype=dtype,trust_remote_code=True,low_cpu_mem_usage=True)
    model.config.use_cache=False
    model=get_peft_model(model,LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,bias="none",task_type="CAUSAL_LM",
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]))
    model.print_trainable_parameters(); model.to("xpu")
    tr=SFTDataset(read_jsonl(TRAIN),tok); dv=SFTDataset(read_jsonl(DEV),tok)
    c=Collate(tok.pad_token_id)
    tl=DataLoader(tr,batch_size=1,shuffle=True,collate_fn=c); dl=DataLoader(dv,batch_size=1,shuffle=False,collate_fn=c)
    params=[p for p in model.parameters() if p.requires_grad]
    opt=torch.optim.AdamW(params,lr=LR,weight_decay=0.01)
    OUT.mkdir(parents=True,exist_ok=True)
    best=1e99; hist=[]; step=0
    for epoch in range(1,EPOCHS+1):
        model.train(); opt.zero_grad(set_to_none=True); losses=[]; t0=time.time()
        for i,b in enumerate(tl,1):
            out=model(**mv(b)); raw=out.loss; (raw/ACCUM).backward(); losses.append(float(raw.detach().cpu()))
            if i%ACCUM==0 or i==len(tl):
                torch.nn.utils.clip_grad_norm_(params,1.0); opt.step(); opt.zero_grad(set_to_none=True); step+=1
                if step%10==0: print(f"epoch={epoch} step={step} loss={losses[-1]:.4f}")
        torch.xpu.synchronize()
        trloss=sum(losses)/len(losses); ev=eval_loss(model,dl)
        rec={"epoch":epoch,"global_step":step,"train_loss":trloss,"eval_loss":ev,"elapsed_sec":time.time()-t0}
        hist.append(rec); print("EPOCH",json.dumps(rec,ensure_ascii=False))
        if ev<best:
            best=ev; d=OUT/"best_adapter"; d.mkdir(parents=True,exist_ok=True); model.save_pretrained(d); tok.save_pretrained(d)
        (OUT/"training_history.json").write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
    d=OUT/"final_adapter"; d.mkdir(parents=True,exist_ok=True); model.save_pretrained(d); tok.save_pretrained(d)
    meta={"base_model":BASE,"device":torch.xpu.get_device_name(0),"epochs":EPOCHS,"max_length":MAXLEN,"best_eval_loss":best,"best_adapter":str(OUT/"best_adapter")}
    (OUT/"metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print("TRAINING COMPLETE"); print(json.dumps(meta,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
