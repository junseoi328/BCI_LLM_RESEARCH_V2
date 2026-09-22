#!/usr/bin/env python3
"""KLUE-WoS(과제지향 대화, CC BY-SA 4.0) 발화를 내려받아 한 줄에 하나씩 저장.
   AAC 표현 사전과 달리 '일상 한국어 문장이 어떻게 이어지는지'를 배우기 위한 것."""
import json, sys, urllib.request, time
OUT = sys.argv[1] if len(sys.argv) > 1 else "corpus_wos.txt"
PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 20
url = ("https://datasets-server.huggingface.co/rows?dataset=klue%2Fklue"
       "&config=wos&split=train&offset={}&length=100")
seen, out = set(), []
for p in range(PAGES):
    try:
        with urllib.request.urlopen(url.format(p*100), timeout=30) as r:
            d = json.load(r)
    except Exception as e:
        print("중단:", e); break
    rows = d.get("rows", [])
    if not rows: break
    for row in rows:
        for turn in row["row"].get("dialogue", []):
            t = (turn.get("text") or "").strip()
            if 2 <= len(t) <= 120 and t not in seen:
                seen.add(t); out.append(t)
    print(f"  {p+1}/{PAGES} 쪽 · 발화 {len(out)}개", flush=True)
    time.sleep(0.2)
open(OUT, "w", encoding="utf-8").write("\n".join(out))
print(f"저장: {OUT} · 발화 {len(out)}개")
