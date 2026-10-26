#!/usr/bin/env python3
"""말뭉치·사전 어휘 -> 지연 로드용 단어 목록 app/static/dict.txt

  python3 tools/build_dict.py <ko_full.txt> <mecab-ko-dic 폴더> [말뭉치.txt ...] > app/static/dict.txt

세 출처를 합친다.
  ① 구어 빈도: hermitdave/FrequencyWords 의 한국어 영화·드라마 자막 어절 빈도
     (OpenSubtitles 2018, CC BY-SA 4.0). 사람들이 실제로 말하는 꼴(어절) 그대로라
     대화 예측에 가장 직접적이다.
  ② 사전 어휘: mecab-ko-dic 2.1.1 (Apache 2.0)의 일반명사·고유명사·부사·감탄사·관형사
     전부, 그리고 동사·형용사는 kiwipiepy 로 활용한 '-다 / -어 / -어요' 꼴.
     빈도가 없는 단어도 빠짐없이 싣는다 — "사전에 있는 말은 다 나온다".
  ③ 빈도 보정: 함께 넘긴 말뭉치 텍스트의 어절 빈도를 더한다.

한 줄에 하나: <단어><빈도 1~9>, 빈도 정보가 없는 사전 단어는 숫자를 생략한다.
빈도 높은 순으로 정렬되어 있어 브라우저는 줄 순서를 그대로 순위로 쓴다.
"""
import collections, csv, glob, math, os, re, sys

H = re.compile(r"^[가-힣]{1,10}$")
sub_path, dic_dir, *corpora = sys.argv[1:]

count = collections.Counter()
for line in open(sub_path, encoding="utf-8"):
    p = line.split()
    if len(p) == 2 and H.match(p[0]):
        count[p[0]] += int(p[1])
count = collections.Counter({w: n for w, n in count.items() if n >= 3})   # 1~2회는 대부분 오탈자

for f in corpora:
    for line in open(f, encoding="utf-8"):
        for w in line.split():
            w = w.strip(".,!?~·\"'()[]…:;")
            if H.match(w):
                count[w] += 1

def rows(name):
    path = os.path.join(dic_dir, name)
    return list(csv.reader(open(path, encoding="utf-8"))) if os.path.exists(path) else []

nouns, plain, cost = set(), set(), {}
for name, is_noun in (("NNG.csv", True), ("NNP.csv", True), ("MAG.csv", False), ("IC.csv", False), ("MM.csv", False)):
    for r in rows(name):
        w = r[0]
        if not H.match(w) or len(w) < 1:
            continue
        (nouns if is_noun else plain).add(w)
        cost[w] = min(cost.get(w, 99999), int(r[3]))

# 동사·형용사: 사전형과 가장 흔한 두 꼴. 불규칙 활용은 kiwi 가 안다(VV-I 등).
from kiwipiepy import Kiwi
kiwi = Kiwi()
for name, tag in (("VV.csv", "VV"), ("VA.csv", "VA")):
    for r in rows(name):
        stem = r[0]
        if not H.match(stem):
            continue
        toks = kiwi.tokenize(stem + "다")
        if not toks or toks[0].form != stem or not toks[0].tag.startswith(tag):
            continue                      # kiwi 가 이 줄기를 모르면 활용을 지어내지 않는다
        t = toks[0].tag
        for ending, etag in (("다", "EF"), ("어", "EF"), ("어요", "EF")):
            form = kiwi.join([(stem, t), (ending, etag)])
            if H.match(form):
                plain.add(form)
                cost[form] = min(cost.get(form, 99999), int(r[3]))

words = set(count) | nouns | plain
mx = max(count.values())
def f(w):
    n = count.get(w, 0)
    return 0 if n == 0 else max(1, min(9, round(math.log1p(n) / math.log1p(mx) * 9)))
order = sorted(words, key=lambda w: (-count.get(w, 0), cost.get(w, 99999), len(w), w))
out = sys.stdout
for w in order:
    k = f(w)   # 빈도 0 은 숫자를 생략한다(전체의 절반이라 그만큼 작아진다)
    out.write(f"{w}{k if k else ''}\n")
print(f"// 단어 {len(order)} · 빈도 있음 {sum(1 for w in order if count.get(w))} · 명사 {len(nouns)}", file=sys.stderr)
