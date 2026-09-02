# BCI LLM 다음 단계 실행 가이드

## 0. 이 패키지의 목적
현재 50-case DEV에서 고정한 v6.3을 더 이상 튜닝하지 않고, **새 150-case unseen TEST**에서 baseline v2와 v6.3을 동일 조건으로 비교한다. 그 다음 EEG top-k decoder contract를 고정한다.

## 1. 프로젝트 루트에 복사
이 ZIP의 `eval/`, `research/`, `docs/`를 `BCI_LLM_RESEARCH_V2` 루트에 그대로 복사한다. 기존 파일을 덮어쓰지 않는 신규 파일들이다.

## 2. Git 체크포인트
```bat
git status
git add app\pipeline\service.py app\llm\diversity_prompt.py app\llm\diversity_generator.py scripts\run_10_sanity.py scripts\debug_conditional.py
git commit -m "feat: freeze v6.3 context-quality ensemble"
git push
```
`.env`는 절대 add 하지 않는다.

## 3. 새 파일 커밋
```bat
git add eval\datasets\test_v1_150.jsonl eval\datasets\test_v1_150_index.csv eval\run_test_v1.py eval\run_benchmark_pair.py research\configs\v6_3_context_quality.txt research\interfaces\eeg_decoder_contract.json research\eeg\validate_decoder_payload.py docs\NEXT_PHASE_EXECUTION_KO.md
git commit -m "research: add frozen unseen test set and benchmark harness"
git push
```

## 4. 코드 검사
```bat
python -m py_compile eval\run_test_v1.py eval\run_benchmark_pair.py research\eeg\validate_decoder_payload.py
python -m pytest -q
```

## 5. 비용 절약 sanity test
먼저 10개만 A/B 비교한다.
```bat
python -m eval.run_benchmark_pair --limit 10
```
오류가 없으면 150개 전체로 간다.

## 6. 최종 unseen TEST A/B
```bat
python -m eval.run_benchmark_pair
```

이 명령은 같은 TEST를 두 번 실행한다.

- `baseline_v2_retest`: `ENSEMBLE_MODE=off`
- `v6_3_context_quality`: `ENSEMBLE_MODE=context_quality`, context/intent threshold 0.72/0.72

중요: TEST 결과를 본 뒤 threshold/prompt를 고치고 같은 TEST를 다시 최종 성능으로 보고하면 안 된다. 수정이 필요하면 test_v1은 validation 성격으로 내려놓고 test_v2를 새로 만들어야 한다.

## 7. 핵심 보고 지표
- Strict Acc@1, Acc@3
- Normalized Acc@1, Acc@3
- Normalized MRR
- mean/P50/P95 latency
- cost/request
- fallback rate
- service error rate

## 8. EEG decoder contract 검증
```bat
python -m research.eeg.validate_decoder_payload
```

박필 측에서 실제 JSON을 받으면:
```bat
python -m research.eeg.validate_decoder_payload path\to\decoder_output.json
```

반드시 `score_type`을 기록한다. classifier probability, decision score, CCA correlation은 같은 값이 아니다.

## 9. 다음 통합 순서
1. unseen TEST에서 v6.3 효과 확인
2. 박필 decoder top-k JSON 확보
3. `/predict`의 `eeg_hypotheses` 입력 연결
4. EEG-language fusion weight는 DEV에서만 조정
5. 새 TEST에서 고정 평가
6. 가빈 UI에 candidate Top-3 + reinput/reject 상태 연결
7. 건강한 참가자/internal pilot 후 실제 연구 절차로 이동

## 10. 테스트셋 구성
`test_v1_150.jsonl`은 10개 범주 × 15문장 = 150문장이다.

- basic_request
- food_drink
- environment
- positioning
- pain_discomfort
- medical_communication
- time_schedule
- social
- questions_answers
- emotion_needs

현재 50-case DEV의 target과 동일한 target 문장은 제외했다.


## 11. 실패 분석
A/B 실행 뒤 생성된 CSV 중 하나를 선택해서:
```bat
python -m eval.analyze_test_failures eval\reports\<CSV파일명>.csv
```
범주별 Acc@1/Acc@3와 normalized miss를 출력한다. TEST 결과를 본 뒤 같은 TEST에 맞춰 prompt/threshold를 조정하지 말고, 실패 원인은 다음 버전 설계 자료로만 사용한다.
