#!/bin/sh
# app/static/dict.txt 전체를 다시 만든다.
#   DATA=<자료 폴더> sh tools/build_dict_all.sh
# 자료 폴더에 필요한 것(저장소에는 싣지 않는다 — 크고, 원문 재배포를 피한다):
#   ko_full.txt              hermitdave/FrequencyWords content/2018/ko/ko_full.txt (CC BY-SA 4.0)
#   mecab-ko-dic-2.1.1-*/    mecab-ko-dic 압축을 푼 폴더 (Apache 2.0)
#   os_ko.txt.gz             OPUS OpenSubtitles v2018 mono/ko.txt.gz
#   wos.txt chat_train.txt   tools/fetch_corpus.py, songys/Chatbot_data (학습분 90%)
#   krdict_*.txt             tools/build_krdict.py 출력 (한국어기초사전, CC BY-SA 2.0 KR)
set -e
D=${DATA:?DATA 폴더를 지정하세요}
P=research/patient_corpus/patient_phrases_ko.txt
OUT=app/static/dict.txt
[ -n "$PATIENT_SRC" ] && cp "$PATIENT_SRC" "$P" || python3 tools/gen_patient_phrases.py > "$P"
# 환자 표현은 30번 반복해 넣는다 — 230만 줄 대사 속에서도 "물 좀 주세요" 같은 이음새가
# 문맥별 상위 목록에 남도록(분야 적응). 반복 수는 bench_decode 로 고른다.
TMP=$(mktemp)
for i in $(seq 30); do cat "$P"; done > "$TMP"
KR=$(mktemp)    # 기초사전 용례: 대사보다 짧고 바른 대화체라 n-gram 에 KRW 배 가중
for i in $(seq ${KRW:-2}); do cat "$D/krdict_corpus.txt"; done > "$KR"
KRWORDS=""; [ "${KR_WORDS:-0}" = 1 ] && KRWORDS="$D/krdict_words.txt"
KRDICT=""; [ "${KR_COUNTS:-1}" = 1 ] && KRDICT="--min2 $D/krdict_corpus.txt"
python3 tools/build_dict.py "$D/ko_full.txt" "$D"/mecab-ko-dic-2.1.1-* "$D/wos.txt" "$D/chat_train.txt" "$TMP" $KRDICT $KRWORDS > "$OUT"
python3 tools/build_ngrams.py --bi-top ${BI_TOP:-20} --tri-top ${TRI_TOP:-6} --tri-min ${TRI_MIN:-4} "$D/os_ko.txt.gz" "$D/chat_train.txt" "$D/wos.txt" "$TMP" "$KR" >> "$OUT"
{ echo "#sit"; cat "$D/krdict_sit.txt"; } >> "$OUT"
rm -f "$KR"
{ echo "#ph"; cat "$P"; } >> "$OUT"
rm -f "$TMP"
wc -c "$OUT"
