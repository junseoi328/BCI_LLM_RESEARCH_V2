# 준서용 — 결제 이후 그대로 실행하는 코드 매뉴얼

## 0. 이 패키지가 추가한 것

- 실제 OpenAI Generator + Context Ranker 분리
- Structured Outputs(JSON Schema)
- `friend`, `schedule`, `entertainment`, `emergency` context 지원
- `ㄷㅇㅈ` 같은 exact 초성 hard filter
- context level ablation (`none / partner / partner_situation / full`)
- EEG Top-k hypothesis normalization/fusion
- semantic near-duplicate filter
- local phrase fallback
- hybrid 전환 기준
- JSONL 실험 logging
- 50개 sanity dataset
- Acc@1 / Acc@3 / MRR / p50/p95 latency / cost 계산
- context ablation 자동 실행
- Luna/Terra/Sol model benchmark 자동 실행
- session/start/predict/select/undo/reset
- 브라우저 test UI `/demo`
- 16개 unit/integration test

---

## 1. 기존 폴더에 적용

기존 `.env`는 따로 보관합니다. 이 패키지에는 실제 `.env`가 없고 `.env.example`만 있습니다.

Windows CMD:

```bat
cd C:\Users\User\Desktop\BCI_LLM_RESEARCH_V2
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m pytest -q
```

정상 기준: `16 passed`.

---

## 2. 결제 전/결제 문제 중에는 Mock

`.env`:

```env
MOCK_MODE=true
DEBUG_MODE=false
```

실행:

```bat
python -m uvicorn app.main:app --reload
```

브라우저:

```text
http://127.0.0.1:8000/demo
```

`ㄷㅇㅈ + 다음 주에 약속 잡을까`를 넣으면 Mock Ranker는 `다음 주`를 1위로 올립니다. 이것은 연결 테스트일 뿐 연구 성능이 아닙니다.

---

## 3. 결제 후 Live OpenAI

`.env`:

```env
MOCK_MODE=false
OPENAI_API_KEY=실제키
OPENAI_GENERATOR_MODEL=gpt-5.6-luna
OPENAI_RANKER_MODEL=gpt-5.6-luna
ALLOW_LOCAL_FALLBACK=true
```

키 확인(키 자체는 출력하지 않음):

```bat
python -c "from app.config import settings; print('mock=', settings.mock_mode); print('key=', bool(settings.openai_api_key)); print('ascii=', settings.openai_api_key.isascii() if settings.openai_api_key else False)"
```

기대:

```text
mock= False
key= True
ascii= True
```

서버 재시작:

```bat
python -m uvicorn app.main:app --reload
```

첫 smoke test:

```bat
python -m scripts.live_smoke_test
```

---

## 4. 10개 sanity test는 `/demo`에서 직접 확인

우선 이런 입력을 수동으로 봅니다.

```text
ㄷㅇㅈ → 도와줘 / 다음 주 (context에 따라 달라져야 함)
ㅁㅈ → 물 줘
ㅂㄲㅈ → 불 꺼줘
ㅈㅅㅂㄲㅈ → 자세 바꿔줘
ㅁㅁㄹ → 목 말라
ㅊㅇ → 추워
ㄱㅁㅇ → 고마워
ㅈㄱㅅㅇ → 자고 싶어
ㅂㄱㅍ → 배고파
ㅇㅍ → 아파
```

이 단계에서는 prompt를 바로 고치지 말고 baseline 결과를 저장합니다.

---

## 5. 50개 데이터 자동 검증

```bat
python -m scripts.validate_dataset
```

기대:

```text
rows=50
dataset validation passed
```

파일:

```text
eval/datasets/sanity_v1.jsonl
```

`target`과 `bci_input`의 초성열이 정확히 일치하는지도 자동 검사합니다.

---

## 6. 50개 Live 평가

연구 성능을 재려면 local fallback이 결과를 오염시키지 않도록 권장:

```env
ALLOW_LOCAL_FALLBACK=false
```

서버를 켤 필요 없이 직접 pipeline을 호출합니다.

```bat
python -m eval.run_eval --context-level full
```

출력:

```text
Acc@1
Acc@3
MRR
Mean latency
p50 latency
p95 latency
Total/mean estimated API cost
Fallback rate
```

CSV와 summary JSON이 `eval/reports/`에 저장됩니다.

---

## 7. Context가 정말 효과 있는지 자동 비교

```bat
python -m eval.run_ablation
```

자동으로 4조건을 비교합니다.

```text
none
partner
partner_situation
full
```

최종 보고서 표:

| Context | Acc@1 | Acc@3 | MRR | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| none | | | | | |
| partner | | | | | |
| partner+situation | | | | | |
| full | | | | | |

이 표가 “문맥이 추천 품질을 개선하는가?”의 첫 연구 결과입니다.

---

## 8. Prompt 개선 방법

코드는 `app/llm/prompts.py`에서 두 개를 분리했습니다.

```text
GENERATOR_INSTRUCTIONS
RANKER_INSTRUCTIONS
```

Generator는 초성만 보고 넓은 후보를 생성합니다.
Ranker가 문맥을 보고 순위를 결정합니다.

변경할 때마다 `.env`의 버전을 올립니다.

```env
GENERATOR_PROMPT_VERSION=generator-v3
RANKER_PROMPT_VERSION=ranker-v3
PIPELINE_VERSION=0.3.0
```

동일 dataset에서 바꾸기 전/후를 비교합니다.

---

## 9. 모델 비교

먼저 Luna로 반복 개발하고, 최종 후보만 비교합니다.

```bat
python -m eval.run_model_benchmark --limit 20 --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol
```

비교 기준:

```text
Acc@3
MRR
p50/p95 latency
API cost
```

가장 비싼 모델을 자동 선택하지 않습니다. BCI에서는 latency와 비용도 성능입니다.

---

## 10. 박필 EEG decoder 연결

권장 request:

```json
{
  "bci_input": "ㄷㅇㅈ",
  "eeg_score_type": "probability",
  "eeg_hypotheses": [
    {"initials": "ㄷㅇㅈ", "score": 0.61},
    {"initials": "ㄷㅇㅊ", "score": 0.22},
    {"initials": "ㅌㅇㅈ", "score": 0.17}
  ],
  "partner": "family",
  "situation": "positioning",
  "recent_context": ["혼자 자세를 바꾸기 어렵다"],
  "top_k": 3
}
```

`score_type`이 classifier probability가 아니라면 거짓으로 probability라고 쓰지 않습니다.

지원:

```text
probability
normalized_evidence
correlation
decision_score
```

`correlation/decision_score`는 확률이라고 주장하지 않고 softmax 기반 bounded ranking weight로만 변환합니다.

---

## 11. 가빈 UI 연결

Frontend는 OpenAI를 직접 호출하지 않고 FastAPI만 호출합니다.

```text
POST /predict
```

UI가 꼭 쓰는 값:

```text
candidates[].candidate_id
candidates[].text
candidates[].rank
fallback
hybrid_action
latency.total_ms
```

---

## 12. Session 기반 문장 완성

선택-확정-되돌리기를 실험하려면:

```text
POST /session/start
POST /session/{session_id}/predict
POST /session/{session_id}/select
POST /session/{session_id}/undo
POST /session/{session_id}/reset
```

현재 session store는 메모리 기반 연구 프로토타입입니다. 서버 재시작 시 사라지며 production DB가 아닙니다.

---

## 13. Auto Toggle

```text
POST /autotoggle/step
```

예:

```json
{"state":{"committed_text":"","initial":null,"medial":null,"final":null},"action":"input","jamo":"ㄷ"}
```

그 다음 `ㅗ`, `commit`으로 `도`를 확정할 수 있습니다.

---

## 14. Hybrid

`experiment_mode="hybrid"`이면 score와 1·2위 margin이 부족할 때:

```json
"hybrid_action": "need_more_input"
```

을 반환합니다.

초기 threshold는 heuristic이므로 participant/eval 결과로 조정해야 합니다.

---

## 15. 연구 로그

기본:

```text
logs/experiment.jsonl
```

기록:

```text
trial/session ID
input/mode/context level
EEG evidence
Top-K
latency
usage/cost
model/prompt/pipeline version
fallback
```

API key, 실명, 전화번호, 환자번호는 기록하지 않습니다.

---

## 16. 지금 실제 순서

```text
[1] 결제/API quota 해결
[2] live smoke test 1회 성공
[3] 10개 수동 sanity test
[4] 50개 sanity_v1 평가
[5] context ablation
[6] 실패 케이스 분류
[7] generator/ranker prompt v3 개선
[8] 같은 50개 재평가
[9] dataset 200~300개로 확대 + dev/test split
[10] Luna/Terra/Sol benchmark
[11] 박필 EEG Top-k 연결
[12] 가빈 UI 연결
[13] Auto Toggle vs Initials
[14] Hybrid
[15] End-to-End 실험
```

가장 중요한 규칙: **평가 데이터의 정답을 보고 prompt에 직접 외우게 만들지 않습니다.** Dev set으로 수정하고 held-out test set으로 최종 평가합니다.
