#!/usr/bin/env python3
"""일반 한국어 대화 말뭉치 -> 앞두단어(트라이그램) 사전.

build_lexicon.py 의 짝. 그쪽이 단어·다음단어를 만든다면 이쪽은 "앞앞단어 +
앞단어 -> 다음단어" 를 만든다. 초성 0개 구간(전체 어절의 약 70%가 여기서
결정된다)에서 앞 한 단어만 보는 것보다 훨씬 좁게 짚어 준다.

원문은 담지 않는다 — 문맥별 상위 후보 목록만 담는다.

    python tools/build_lex_trigrams.py corpus.txt > build/lex_trigrams.js

측정 (tools 의 held-out 일반 대화 300문장 기준):
    끔                      절감 33.8% · 초성 0개 적중 35.9%
    1,734 문맥 (MIN_N=5)    절감 36.4% · 40.1%   gzip 약 15KB
    3,983 문맥 (MIN_N=3)    절감 37.1% · 41.4%   gzip 약 36KB   <- 채택
검수된 AAC 표현이 목표일 때는 변화가 없다(해도 없다). 말뭉치가 과제지향
대화라 표현 사전과 단어 짝이 거의 겹치지 않기 때문 — 일반 대화에서만
효과가 보인다.
"""
from __future__ import annotations

import collections
import json
import re
import sys

MIN_N = 3        # 이 횟수 미만으로 나온 트라이그램은 버린다
TOP_PER_CTX = 3  # 문맥 하나당 남길 다음 단어 수
MAX_WORD = 12    # 이보다 긴 어절은 오탈자로 보고 버린다

TOKEN = re.compile(r"[^가-힣\s]")


def build(text: str) -> list[list]:
    tri: collections.Counter = collections.Counter()
    for line in text.split("\n"):
        words = [w for w in TOKEN.sub(" ", line).split() if w and len(w) <= MAX_WORD]
        for i in range(2, len(words)):
            tri[(words[i - 2], words[i - 1], words[i])] += 1

    # 빈도 높은 것부터 채우면 문맥당 상위 N 개가 자연스럽게 남는다
    by_ctx: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for (a, b, c), n in sorted(tri.items(), key=lambda kv: -kv[1]):
        if n < MIN_N:
            break
        if len(by_ctx[(a, b)]) < TOP_PER_CTX:
            by_ctx[(a, b)].append(c)

    # 키는 script_v4.js 의 CTX_SEP 과 같은 U+0001 로 잇는다
    return [[a + "\u0001" + b, nexts] for (a, b), nexts in by_ctx.items()]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        rows = build(fh.read())
    body = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    print("/* 자동 생성 — tools/build_lex_trigrams.py. 원문이 아니라 빈도 상위 목록이다. */")
    print(f"const LEX_TRIGRAMS={body};")
    print(f"// 문맥 {len(rows)}개 · MIN_N={MIN_N} · 문맥당 {TOP_PER_CTX}개", file=sys.stderr)


if __name__ == "__main__":
    main()
