# V7 설계 결정

## 1. Fine-tuning 목표를 "문맥 ranking"이 아니라 "candidate coverage"로 제한
현재 코드에서 base generator는 `generate_candidates(initials, count)` 형태이며,
대화 문맥은 이후 ranker에서 사용된다. 따라서 현재 architecture를 깨지 않으면서 실제 weight training을 하려면
generator가 초성에 맞는 **더 넓고 BCI에 유용한 후보 pool**을 생성하도록 SFT하는 것이 가장 안전하다.

## 2. Runtime training prompt 정합성
`training.export_openai_sft`는 가능한 경우 현재 프로젝트의:
- `GENERATOR_INSTRUCTIONS`
- `build_generator_input`
을 import해서 학습 JSONL을 만든다.

즉 학습 prompt와 실제 inference prompt의 mismatch를 줄인다.

## 3. Hard constraints는 계속 Python
Fine-tune 후에도:
- 초성 exact match
- duplicate 제거
- schema validation
- Top-K
는 deterministic code가 담당한다.

## 4. Phrase memory
Fine-tuning은 희귀 문구를 100% 보장하지 않는다.
따라서 TRAIN catalog에서 만든 local phrase memory를 candidate pool에 추가한다.
이 memory는 API가 아니므로 latency/cost 증가가 거의 없다.

## 5. DEV와 TEST
- SFT validation/dev는 모델 선택 가능
- locked final test는 최종 고정 평가에만 사용
- final test를 보고 수정하면 새 test_v2 필요

## 6. 다음 버전
v7 이후 실제 EEG를 받으면:
EEG Top-k → candidate generation → context ranking → EEG-language fusion → SSVEP selection
