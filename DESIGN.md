# BCI LLM Research v0.2 — 설계 결정

## 목표

`EEG evidence + Korean partial input + conversational context → ranked Korean Top-K`.

## 분리 원칙

- Korean hard constraint: Python
- Candidate generation: LLM generator
- Context/partner ranking: LLM ranker
- EEG evidence normalization/fusion: Python
- Final user choice: SSVEP/UI

## 현재 연구 가설

1. `initials + context`가 `initials only`보다 Acc@3/MRR를 높이는가?
2. EEG Top-k evidence + language rank가 EEG argmax만 사용할 때보다 의도 복원률을 높이는가?
3. Initials/Auto Toggle/Hybrid 중 어떤 방법이 선택 횟수와 completion time을 최소화하는가?

## 확률 해석 주의

LLM의 context/language score와 현재 `final_score`는 calibrated probability가 아니다. EEG score도 classifier 종류에 따라 probability가 아닐 수 있다. v0.2의 fusion은 heuristic ranking이다.

## 연구 결과에서 반드시 함께 보고할 것

- Acc@1, Acc@3, MRR
- p50/p95 latency
- API cost/request
- valid candidate / fallback rate
- EEG 통합 후 selection count, KSR, completion time, correction count
- model / prompt / pipeline / dataset version
