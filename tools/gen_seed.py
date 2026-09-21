#!/usr/bin/env python3
"""로컬 후보 인덱스 생성기.

research/phrase_memory/approved_bci_phrase_bank_v2.jsonl -> build/seed.js
문장 후보(=검수된 표현 그대로)와 단어 후보를 둘 다 뽑는다. 이 인덱스 덕분에
초성 입력 즉시(0ms, 클라우드 호출 없이) 후보가 뜨고, 언어 모델은 로컬이
못 맞춘 나머지만 채운다.  phrase bank가 늘어나면 이 스크립트를 다시 돌린다.
"""
import json, sys, collections, pathlib

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def choseong(text):
    out = []
    for ch in text:
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3:
            out.append(CHO[(c - 0xAC00) // 588])
        elif ch in CHO:
            out.append(ch)
    return "".join(out)

src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                   "research/phrase_memory/approved_bci_phrase_bank_v2.jsonl")
rows = [json.loads(l) for l in src.open(encoding="utf-8") if l.strip()]

cats = sorted({r.get("category", "") for r in rows})
cat_i = {c: i for i, c in enumerate(cats)}

phrases, seen = [], set()
for r in rows:
    text = r["text"].strip()
    ini = r.get("initials") or choseong(text)
    if not ini or (ini, text) in seen:
        continue
    seen.add((ini, text))
    phrases.append([ini, text, cat_i[r.get("category", "")]])

# 단어 후보: 문장을 어절로 쪼개고 빈도를 센다. 같은 단어가 여러 카테고리에
# 나오면 가장 자주 나온 카테고리를 대표로 삼는다.
wfreq = collections.Counter()
wcat = collections.defaultdict(collections.Counter)
for r in rows:
    ci = cat_i[r.get("category", "")]
    for w in r["text"].split():
        w = w.strip(".,!?·").strip()
        if not w or len(w) > 12 or not choseong(w):
            continue
        wfreq[w] += 1
        wcat[w][ci] += 1
words = [[choseong(w), w, n, wcat[w].most_common(1)[0][0]] for w, n in wfreq.most_common()]

# 다음 단어 예측용 바이그램. "물" 다음에 무엇이 오는지 알면 초성을 한 글자도
# 누르지 않고 후보를 띄울 수 있다 — 가장 큰 타건 절감은 여기서 나온다.
# "" 키는 문장 첫 단어(=시작 분포).
bi = collections.defaultdict(collections.Counter)
for r in rows:
    prev = ""
    for w in r["text"].split():
        w = w.strip(".,!?·").strip()
        if not w:
            continue
        bi[prev][w] += 1
        prev = w
bigrams = [[prev, [[w, n] for w, n in c.most_common(6)]] for prev, c in bi.items() if c]

j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "build/seed.js")
out.write_text(
    "/* 자동 생성 — tools/gen_seed.py. 직접 고치지 말고 스크립트를 다시 돌릴 것. */\n"
    f"const SEED_CATS={j(cats)};\n"
    f"const SEED_PHRASES={j(phrases)};\n"
    f"const SEED_WORDS={j(words)};\n"
    f"const SEED_BIGRAMS={j(bigrams)};\n", encoding="utf-8")
print(f"카테고리 {len(cats)} / 문장 {len(phrases)} / 단어 {len(words)} / 바이그램 {len(bigrams)}"
      f" -> {out} ({out.stat().st_size//1024}KB)")
