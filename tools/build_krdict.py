#!/usr/bin/env python3
"""한국어기초사전(국립국어원, CC BY-SA 2.0 KR) 내려받기 엑셀 -> 학습 재료 네 가지.

  python3 tools/build_krdict.py <출력폴더> 1_30000_*.xls 2_30000_*.xls 3_16833_*.xls

출력
  krdict_corpus.txt  용례 문장·대화 한 줄에 하나(학습용 98%). n-gram·단어 빈도 학습에 쓴다.
  krdict_test.txt    학습에서 뺀 대화 300줄 — 효과를 재는 보류 세트.
  krdict_words.txt   표제어와 활용형. 어휘 등급만큼 반복(초급 30·중급 10·고급 3)해 빈도 대신 쓴다.
  krdict_sit.txt     화면의 상황(식사·통증·병원…)마다 그 상황 용례에 유난히 자주 나오는 말 —
                     dict.txt 의 #sit 구역. 상황을 고르면 이 말들이 앞으로 온다(적재적소).
원문 전체는 저장소에 싣지 않는다. 사전 엑셀은 krdict.korean.go.kr 에서 내려받는다.
"""
import collections, json, math, random, re, sys, zlib
import xlrd
from kiwipiepy import Kiwi

outdir, *files = sys.argv[1:]
H = re.compile(r"^[가-힣]{1,10}$")
COLS = ["표제어", "구분", "품사", "어휘 등급", "의미 범주", "주제 및 상황 범주", "활용", "용례", "부표제어 용례"]

# 화면의 상황 -> 사전의 의미 범주(앞부분 일치)·주제 및 상황 범주
SIT = {
  "meal":          (["식생활"], ["요리 설명하기", "음식 주문하기", "음식 설명하기", "식문화"]),
  "pain":          (["삶 > 병과 증상", "인간 > 신체 부위", "인간 > 감각", "인간 > 생리 현상", "인간 > 체력 상태",
                     "인간 > 신체 변화", "인간 > 신체 내부 구성"], ["건강"]),
  "hospital":      (["삶 > 치료 행위", "삶 > 약품류", "삶 > 병과 증상"], ["보건과 의료", "병원 이용하기", "약국 이용하기", "건강"]),
  "positioning":   (["개념 > 위치 및 방향", "인간 > 신체 행위", "인간 > 신체에 가하는 행위"], ["위치 표현하기"]),
  "home":          (["주생활", "의생활", "삶 > 일상 행위", "삶 > 친족 관계"],
                    ["집안일", "주거 생활", "하루 생활", "소개하기(가족 소개)", "가족 행사"]),
  "schedule":      (["개념 > 시간", "개념 > 순서", "개념 > 빈도"],
                    ["시간 표현하기", "날짜 표현하기", "요일 표현하기", "약속하기", "주말 및 휴가"]),
  "entertainment": (["삶 > 여가 활동", "삶 > 여가 도구", "삶 > 여가 시설", "문화 > 음악", "문화 > 대중 문화",
                     "스포츠", "사회 생활 > 매체"],
                    ["취미", "여가 생활", "대중 문화", "대중 매체", "공연과 감상", "영화 보기", "스포츠"]),
  "emergency":     (["삶 > 병과 증상"], ["사건", "사고", "재해 기술하기"]),
  "general":       (["인간 > 감정"], ["인사하기", "감사하기", "사과하기", "기분 표현하기", "감정", "인간관계"]),
}
GRADE = {"초급": 30, "중급": 10, "고급": 3}

def utterances(text):
    """용례 칸 -> 문장·대화 발화. <구>(구 단위 예시)는 문장이 아니라 뺀다."""
    for line in text.split("\n"):
        m = re.match(r"<(문장|대화)>\s*(?:[가나]:\s*)?(.*)", line.strip())
        if m:
            s = m.group(2).strip()
            if s and "~" not in s:
                yield m.group(1), s

kiwi = Kiwi()
corpus, test_pool, words = [], [], collections.Counter()
sit_test = []                                     # (상황, 보류 대화) — 상황 가중 효과를 잴 때
usage, generated = collections.Counter(), set()   # 용례에 실제로 나온 어절 / kiwi 로 지은 꼴
sit_tok = {s: collections.Counter() for s in SIT}
all_tok = collections.Counter()
for f in files:
    wb = xlrd.open_workbook(f, on_demand=True); sh = wb.sheet_by_index(0)
    idx = {sh.cell_value(0, c): c for c in range(sh.ncols)}
    for r in range(1, sh.nrows):
        row = {k: str(sh.cell_value(r, idx[k])).strip() for k in COLS if k in idx}
        head = row["표제어"].replace("-", "").replace("^", " ").strip()
        # 결정적으로 2% 를 보류 세트로(표제어 기준이라 같은 항목의 용례가 양쪽에 갈리지 않는다)
        held = zlib.crc32(head.encode()) % 50 == 0
        utts = list(utterances(row["용례"] + "\n" + row.get("부표제어 용례", "")))
        for kind, s in utts:
            (test_pool if held and kind == "대화" else corpus).append(s) if not (held and kind != "대화") else None
        # 단어: 표제어 + 활용형 + (동사·형용사) 해요체
        w = GRADE.get(row["어휘 등급"], 1)
        pos = row["품사"]
        forms = set()
        if row["구분"] in ("단어", "부표제어") and H.match(head):
            forms.add(head)
        for x in row["활용"].split(","):
            x = re.sub(r"\[.*?\]", "", x).strip()
            if H.match(x): forms.add(x)
        if pos in ("동사", "형용사") and head.endswith("다") and H.match(head):
            stem = head[:-1]
            toks = kiwi.tokenize(head)
            if toks and toks[0].form == stem:
                for e in ("어", "어요", "었어요"):
                    form = kiwi.join([(stem, toks[0].tag), ("었" if e == "었어요" else e, "EP" if e == "었어요" else "EF")]
                                     + ([("어요", "EF")] if e == "었어요" else []))
                    # 되짚어 읽어 같은 줄기가 나올 때만 쓴다("나다" -> "나어" 같은 잘못 지은 꼴을 거른다)
                    back = kiwi.tokenize(form) if H.match(form) else None
                    if back and back[0].form == stem: forms.add(form); generated.add(form)
        for x in forms: words[x] += w
        # 상황별 말: 그 상황 항목의 표제어·활용형 + 용례에 나온 어절
        sem, topic = row["의미 범주"], row["주제 및 상황 범주"]
        toks = [t.strip(".,!?~\"'") for _, s in utts for t in s.split()]
        toks = [t for t in toks if H.match(t)]
        usage.update(toks)
        toks += list(forms)
        for t in toks: all_tok[t] += 1
        for s, (sems, topics) in SIT.items():
            if any(sem.startswith(x) for x in sems) or any(t in topic for t in topics):
                if held:
                    sit_test += [(s, u) for k, u in utts if k == "대화"]
                else:
                    for t in toks: sit_tok[s][t] += 1     # 보류 항목은 상황 목록 학습에서도 뺀다
    wb.release_resources()

# 지은 꼴은 용례에 한 번이라도 실제로 쓰인 것만 남긴다("나다" -> "나어" 같은 것 제거)
bad = {w for w in generated if not usage[w]}
for c in [words, all_tok, *sit_tok.values()]:
    for w in bad: c.pop(w, None)
random.Random(7).shuffle(test_pool)
test = [s for s in test_pool if 2 <= len(s.split()) <= 10][:300]
open(f"{outdir}/krdict_corpus.txt", "w", encoding="utf-8").write("\n".join(corpus))
open(f"{outdir}/krdict_test.txt", "w", encoding="utf-8").write("\n".join(test))
random.Random(7).shuffle(sit_test)
sit_test = [(s, u) for s, u in sit_test if s != "general" and 2 <= len(u.split()) <= 10][:300]
open(f"{outdir}/krdict_test_sit.txt", "w", encoding="utf-8").write("\n".join(f"{s}\t{u}" for s, u in sit_test))
with open(f"{outdir}/krdict_words.txt", "w", encoding="utf-8") as fh:
    for w, n in words.items(): fh.write((w + " ") * min(n, 60) + "\n")
# 상황 특이도: 그 상황 안 빈도가 전체 빈도에 비해 얼마나 큰가(로그 비율, 3회 이상)
with open(f"{outdir}/krdict_sit.txt", "w", encoding="utf-8") as fh:
    for s, c in sit_tok.items():
        tot_s, tot = sum(c.values()), sum(all_tok.values())
        # 문어체 희귀어가 위로 오지 않게 전체에서 8번 이상 나온 말만, 상황 안 빈도에 더 무게
        score = {w: math.log((n / tot_s) / (all_tok[w] / tot)) * n ** 0.7 for w, n in c.items() if n >= 3 and all_tok[w] >= 8}
        top = [w for w, v in sorted(score.items(), key=lambda x: -x[1]) if v > 0][:800]
        fh.write(f"{s}\t{' '.join(top)}\n")
print(f"// 용례 {len(corpus)}줄 · 보류 {len(test)} · 단어 {len(words)} · 상황 {len(sit_tok)}", file=sys.stderr)
