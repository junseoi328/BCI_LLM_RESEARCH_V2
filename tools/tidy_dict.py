#!/usr/bin/env python3
"""단어 목록 다듬기 — build_dict.py 다음에 돈다(build_dict_all.sh).

  python3 tools/tidy_dict.py app/static/dict.txt <mecab-ko-dic 폴더> <krdict_words.txt> <대화·환자·용례 말뭉치 ...>

ㅋㅇㅎ → '키요하루'처럼 영화 자막(OpenSubtitles)의 인물 이름이 빈도만으로 앞에 나와 어색했다.
kiwipiepy로 어절의 첫 형태소가 명사인데 그 명사가 mecab-ko-dic(명사·부사·감탄사 등)에도,
한국어기초사전 표제어에도 없고, 대화·환자·사전 용례 말뭉치에도 한 번도 안 나온 어절만 골라
빈도 숫자를 떼고 사전 단어 뒤로 옮긴다. 지우지 않으므로 초성을 끝까지 치면 여전히 나온다.

② '쾌유해'처럼 기초사전의 '…하다' 동사가 자막에 드물어 활용꼴이 아예 없던 문제:
표제어 X하다마다 X해·X해요·X했어·X하세요 중 목록에 없는 꼴을 빈도 있는 어절 바로 뒤에 더한다.
"""
import csv, glob, re, sys
from kiwipiepy import Kiwi

path, dic_dir, krwords, *corpora = sys.argv[1:]
known = set()
for tag in ("NNG", "NNP", "NNB", "NP", "NR", "MAG", "MAJ", "IC", "MM", "XR"):
    for f in glob.glob(f"{dic_dir}/{tag}*.csv"):
        known.update(r[0] for r in csv.reader(open(f, encoding="utf-8")))
hada = []
for line in open(krwords, encoding="utf-8"):
    w = line.split(" ", 1)[0]
    known.add(w)
    if w.endswith("하다") and len(w) >= 4:
        known.add(w[:-2])
        hada.append(w[:-2])
seen = set()
for f in corpora:
    for line in open(f, encoding="utf-8"):
        seen.update(w.strip(".,!?~·\"'()[]…:;") for w in line.split())

lines = open(path, encoding="utf-8").read().split("\n")
end = next(i for i, l in enumerate(lines) if l.startswith("#"))
head, tail = lines[:end], lines[end:]
pat = re.compile(r"^([가-힣]+)(\d)$")
cand = [(i, m.group(1)) for i, l in enumerate(head) if (m := pat.match(l)) and m.group(1) not in seen]
odd = set()
for (i, w), res in zip(cand, Kiwi().analyze([w for _, w in cand], top_n=1)):
    toks = res[0][0]
    if toks and toks[0].tag in ("NNG", "NNP") and len(toks[0].form) >= 2 and toks[0].form not in known:
        odd.add(i)
keep = [l for i, l in enumerate(head) if i not in odd]
moved = [pat.match(head[i]).group(1) for i in sorted(odd)]
have = {pat.match(l).group(1) if pat.match(l) else l for l in head}
forms = [x + e for x in dict.fromkeys(hada) for e in ("해", "해요", "했어", "하세요") if x + e not in have]
# 기초사전(약 5만 표제어) 활용꼴은 빈도 없는 mecab 단어(쾌연히 같은 드문 말)보다 앞에 둔다
cut = next((i for i, l in enumerate(keep) if not pat.match(l)), len(keep))
open(path, "w", encoding="utf-8").write("\n".join(keep[:cut] + forms + keep[cut:] + moved + tail))
print(f"뒤로 보낸 어절 {len(moved)}개 · 더한 하다 활용꼴 {len(forms)}개", file=sys.stderr)
