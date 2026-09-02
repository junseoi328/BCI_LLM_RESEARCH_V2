from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
CHO=["ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]
PUNCT=re.compile(r"""[.,!?~…'"“”‘’·:;()\[\]{}<>]""")
def extract_initials(text:str)->str:
    out=[]
    for ch in unicodedata.normalize("NFC",text or ""):
        c=ord(ch)
        if 0xAC00<=c<=0xD7A3: out.append(CHO[(c-0xAC00)//588])
        elif ch in CHO: out.append(ch)
    return "".join(out)
def normalize_text(text:str)->str:
    text=unicodedata.normalize("NFC",text or "").strip()
    text=re.sub(r"\s+","",text)
    return PUNCT.sub("",text)
def read_jsonl(path):
    rows=[]
    with Path(path).open("r",encoding="utf-8-sig") as f:
        for i,line in enumerate(f,1):
            line=line.strip()
            if line: rows.append(json.loads(line))
    return rows
def safe_json_candidates(text:str)->list[str]:
    text=(text or "").strip()
    tries=[text]
    a,b=text.find("{"),text.rfind("}")
    if a>=0 and b>a: tries.append(text[a:b+1])
    for t in tries:
        try:
            obj=json.loads(t); vals=obj.get("candidates",[])
            if isinstance(vals,list): return [str(x).strip() for x in vals if str(x).strip()]
        except Exception: pass
    return []
