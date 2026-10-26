#!/usr/bin/env python3
"""대화 말뭉치 -> 사전 파일 뒤에 붙일 '다음 단어' 표 두 개.

  python3 tools/build_ngrams.py [--bi-min N] [--tri-min N] <말뭉치.txt|.gz ...> >> app/static/dict.txt

#bi   앞단어<TAB>전체횟수<TAB>다음1:횟수 다음2:횟수 …   (앞단어가 빈 칸 = 말의 첫 단어)
#tri  앞앞단어 앞단어<TAB>전체횟수<TAB>다음1:횟수 …
#end  단어<TAB>그 단어로 말이 끝난 비율  — 한국어는 서술어가 끝에 오므로 "줘·돼·싶다"는
      말끝에 잘 오고 "좀·안·이"는 거의 안 온다. 띄어쓰기 없는 초성 문장을 나눌 때 쓴다.

원문은 싣지 않는다 — 문맥마다 가장 자주 이어진 단어 몇 개와 그 횟수만 남긴다.
브라우저는 이 횟수로 P(다음 | 앞 두 단어) -> P(다음 | 앞 단어) -> P(단어) 순으로
물러서며(stupid backoff) 초성에 맞는 단어를 줄 세운다.
말뭉치: OPUS OpenSubtitles 2018 한국어(영화·드라마 대사, Lison & Tiedemann 2016),
songys/Chatbot_data(MIT), KLUE-WoS(CC BY-SA 4.0).
"""
import collections, gzip, re, sys

args = sys.argv[1:]
def opt(name, default):
    if name in args:
        i = args.index(name); v = int(args[i + 1]); del args[i:i + 2]; return v
    return default
BI_MIN, TRI_MIN = opt("--bi-min", 3), opt("--tri-min", 3)
BI_TOP, TRI_TOP = opt("--bi-top", 30), opt("--tri-top", 10)
H = re.compile(r"^[가-힣]{1,10}$")
STRIP = ".,!?~·\"'()[]{}<>:;…-♪*"

bi = collections.defaultdict(collections.Counter)
uni = collections.Counter(); ends = collections.Counter()
tri = collections.defaultdict(collections.Counter)
for path in args:
    fh = gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else open(path, encoding="utf-8")
    for line in fh:
        p1 = p2 = ""
        for raw in line.split():
            w = raw.strip(STRIP)
            if not H.match(w):
                p1 = p2 = ""          # 숫자·외국어·기호가 끼면 문맥을 끊는다
                continue
            bi[p2][w] += 1
            uni[w] += 1
            if p2:
                tri[p1 + " " + p2][w] += 1
            p1, p2 = p2, w
            if raw[-1:] in ".?!":     # 문장이 끝나면 다음 단어는 '첫 단어'
                ends[w] += 1
                p1 = p2 = ""
        if p2:                        # 줄 끝도 말의 끝으로 본다(대사·발화가 한 줄씩이다)
            ends[p2] += 1

out = sys.stdout
out.write("#bi\n")
nb = 0
for prev, c in bi.items():
    top = [f"{w}:{n}" for w, n in c.most_common(BI_TOP) if n >= BI_MIN]
    if top:
        out.write(f"{prev}\t{sum(c.values())}\t{' '.join(top)}\n"); nb += 1
out.write("#tri\n")
nt = 0
for key, c in tri.items():
    top = [f"{w}:{n}" for w, n in c.most_common(TRI_TOP) if n >= TRI_MIN]
    if top:
        out.write(f"{key}\t{sum(c.values())}\t{' '.join(top)}\n"); nt += 1
out.write("#end\n")
ne = 0
for w, n in uni.items():
    if n >= 20:
        r = ends[w] / n
        if r >= 0.01:
            out.write(f"{w}\t{r:.2f}\n"); ne += 1
print(f"// 말끝 {ne} 단어", file=sys.stderr)
print(f"// 다음단어 {nb} 문맥 · 앞두단어 {nt} 문맥 (최소 {BI_MIN}/{TRI_MIN}회)", file=sys.stderr)
