#!/usr/bin/env python3
"""일반 한국어 대화 말뭉치 -> 단어/다음단어 사전 (브라우저에 실어 보낼 크기로).

  사용: python3 tools/build_lexicon.py <텍스트파일...> -o build/lexicon.js [--words N] [--bigrams N]

검수된 AAC 표현 사전(gen_seed.py)과 역할이 다르다. 그쪽은 '정확히 이 말을
하고 싶다'를 맞히는 고정밀 층이고, 이쪽은 '한국어 문장이 대체로 어떻게
이어지는가'를 아는 넓고 성긴 층이다. 후보 점수에서도 더 낮은 무게를 받는다.
말뭉치 원문은 싣지 않는다 — 빈도표만 만든다.
"""
import sys, re, json, collections, pathlib

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def choseong(t):
    o=[]
    for ch in t:
        c=ord(ch)
        if 0xAC00<=c<=0xD7A3: o.append(CHO[(c-0xAC00)//588])
        elif ch in CHO: o.append(ch)
    return "".join(o)

HANGUL = re.compile(r"^[가-힣]+$")
def clean(w):
    w = w.strip(" .,!?~·\"'()[]{}<>:;…").strip()
    return w if HANGUL.match(w or "") and 1 <= len(w) <= 8 else None

# -o 와 --words/--bigrams 의 "값"은 입력 파일이 아니다
flags={"-o","--words","--bigrams"}
argv=sys.argv[1:]; args=[]; skip=False
for i,a in enumerate(argv):
    if skip: skip=False; continue
    if a in flags: skip=True; continue
    if a.startswith("-"): continue
    args.append(a)
def opt(name, default):
    return int(sys.argv[sys.argv.index(name)+1]) if name in sys.argv else default
out = pathlib.Path(sys.argv[sys.argv.index("-o")+1] if "-o" in sys.argv else "build/lexicon.js")
MAXW, MAXB = opt("--words", 9000), opt("--bigrams", 14000)

wf = collections.Counter(); bi = collections.defaultdict(collections.Counter)
lines = 0
for f in args:
    for line in pathlib.Path(f).open(encoding="utf-8"):
        line = line.strip()
        if not line: continue
        lines += 1
        prev = ""
        for raw in line.split():
            w = clean(raw)
            if not w:
                prev = ""; continue
            wf[w] += 1
            bi[prev][w] += 1
            prev = w

# 초성은 단어에서 바로 계산할 수 있으므로 파일에 싣지 않는다(용량의 약 1/3).
# 빈도도 원수치 대신 로그 눈금(0~9)으로 줄인다 — 순위만 가르면 충분하다.
import math
top = [(w, n) for w, n in wf.most_common(MAXW) if choseong(w)]
mx = max((n for _, n in top), default=1)
words = [[w, max(0, min(9, int(math.log1p(n) / math.log1p(mx) * 9)))] for w, n in top]
pairs = sorted(((p, w, n) for p, c in bi.items() for w, n in c.items() if n >= 2),
               key=lambda t: -t[2])[:MAXB]
grouped = collections.defaultdict(list)
for p, w, n in pairs: grouped[p].append((w, n))
bigrams = [[p, [w for w, _ in sorted(v, key=lambda x: -x[1])[:4]]] for p, v in grouped.items()]

j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("/* 자동 생성 — tools/build_lexicon.py. 원문이 아니라 빈도표다. */\n"
               f"const LEX_WORDS={j(words)};\nconst LEX_BIGRAMS={j(bigrams)};\n", encoding="utf-8")
print(f"문장 {lines} · 단어 {len(words)} · 다음단어 {len(bigrams)}쌍 -> {out} ({out.stat().st_size//1024}KB)")
