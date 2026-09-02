# BCI V7 DATASET V2 + FINE-TUNING COMPLETE

이 패키지는 이전 v1 review의 문제를 수정한 전체 workflow다.

## 핵심 변경
1. 검토 단위를 "반복된 후보 리스트"가 아니라 **후보 한 문장당 한 행**으로 변경.
2. initial-group 단위 TRAIN/DEV 분리.
3. 기존 benchmark `test_v1_150`과 exact normalized overlap은 기본적으로 seed에서 제외.
4. 600 TRAIN / 100 DEV / 50 HARD를 자동 구축.
5. 현재 GPT-5.6 Luna generator를 teacher로 사용해 후보 pool을 선택적으로 확장 가능.
6. teacher 후보는 자동 승인하지 않고 `approved=0`으로 검토하게 함.
7. 실제 OpenAI SFT job 생성/상태확인/benchmark/full-pipeline 통합 코드 포함.
8. 기존 Excel review 파일도 `migrate_legacy_review.py`로 읽을 수 있음.

## 추천 실행 순서

```bat
cd C:\Users\User\Desktop\BCI_LLM_RESEARCH_V2
.venv\Scripts\activate

pip install -r requirements-v7-v2.txt

python -m pytest -q
scripts_v7\00_BUILD_SEED.bat
```

먼저:
`training_v2\reviews\candidate_pool_review_v2.csv`
를 확인한다.

### 기존 Excel review를 가져오고 싶으면
```bat
python -m training_v2.migrate_legacy_review --input "dev_review_v1.csv.xlsx"
```
결과의 legacy 후보는 `approved=0`이므로 좋은 표현만 직접 1로 변경한다.

### Teacher augmentation은 선택
API 비용이 들지만 더 강한 후보 pool을 만들고 싶으면. 기본값은 비용/시간 보호를 위해 우선순위 높은 80개 initial group만 1회씩 호출한다:
```bat
scripts_v7\01_TEACHER_AUGMENT_OPTIONAL.bat
```

그 뒤:
`training_v2\reviews\teacher_candidate_review.csv`
를 Excel에서 열어 teacher_generator 행 중 좋은 표현만 `approved=1`로 바꾼다.

CSV 대신 `.xlsx`로 저장해도 finalize가 읽을 수 있다.

### Seed만으로 먼저 학습할 때
```bat
scripts_v7\02_FINALIZE_DATASET_FROM_SEED.bat
```

### Teacher review까지 반영할 때
```bat
scripts_v7\02B_FINALIZE_AFTER_TEACHER_REVIEW.bat
```

결과:
- `training_v2\data\train_semantic_v2.jsonl` 600
- `training_v2\data\dev_semantic_v2.jsonl` 100
- `training_v2\data\hard50_v2.jsonl` 50

검증:
```bat
python -m training_v2.validate_dataset
```
반드시 `DATASET V2 VALID`.

### OpenAI SFT JSONL
```bat
scripts_v7\03_EXPORT_SFT.bat
```

생성:
- `training_v2\data\openai\train_sft_v2.jsonl`
- `training_v2\data\openai\dev_sft_v2.jsonl`

### 실제 Fine-tuning 시작
현재 공식 `/v1/fine_tuning/jobs` 지원 snapshot 기준 기본값:
`gpt-4.1-mini-2025-04-14`

```bat
scripts_v7\04_CREATE_FINE_TUNE_JOB.bat
```

Fine-tuning Dashboard:
https://platform.openai.com/finetune

### 학습 상태 확인
```bat
scripts_v7\05_WATCH_FINE_TUNE.bat
```

성공하면:
`training_v2\artifacts\ft_model_v2.json`
에 `fine_tuned_model=ft:...` 저장.

### Fine-tuned generator가 실제로 좋아졌는지
```bat
scripts_v7\06_BENCHMARK_GENERATOR.bat
```

핵심:
- mean_gold_recall
- any_gold_hit_rate
- mean_initial_valid_rate
- latency

### 전체 BCI LLM pipeline 비교
```bat
scripts_v7\07_BENCHMARK_PIPELINE_HARD50.bat
```

비교:
- v6.3: Luna generator + Luna ranker
- v7: fine-tuned generator + Luna ranker

### v7을 실제 /predict 기본 generator로 설치
DEV/HARD 결과가 좋을 때만:
```bat
python -m scripts_v7.install_v7_factory
```

`.env`:
```env
V7_FT_ENABLED=true
FT_GENERATOR_MODEL=ft:gpt-4.1-mini-2025-04-14:...
```

그 뒤:
```bat
python -m py_compile app\pipeline\service.py app\llm\fine_tuned_generator_v2.py app\llm\factory_v7_v2.py
python -m pytest -q
python -m scripts.live_smoke_test
```

원복:
```bat
python -m scripts_v7.uninstall_v7_factory
```

## 연구 원칙
- `test_v1_150`은 이미 결과를 본 benchmark다. 이제 final unseen test가 아니다.
- V7을 고정한 뒤 새 `test_v2_final`을 만들어 한 번만 최종 평가한다.
- Fine-tuning은 generator candidate coverage 개선용.
- context ranking은 기존 Luna ranker가 담당.
- 초성 exact validation은 계속 Python hard constraint.
- 실제 EEG 연결 전에 LLM v7을 freeze한다.


## 데이터 균형
TRAIN 600은 단순 random oversampling이 아니라 category quota를 사용한다.
기본 목표는 medical/pain/positioning과 고중의성 ambiguity를 조금 더 많이 두되,
나머지 일상/사회/기기/환경 카테고리도 모두 유지하는 것이다.
