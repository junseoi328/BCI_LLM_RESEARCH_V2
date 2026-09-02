# BCI V7 Fine-tuning Complete Package

목표: 현재 v6.3 파이프라인의 구조를 유지하면서 **generator coverage만 소규모 SFT로 강화**하고,
기존 문맥 ranker + deterministic Korean filter + conditional diversity를 그대로 활용한다.

## 왜 generator만 fine-tune?
현재 pipeline은 내부적으로 많은 후보를 생성한 뒤 Python exact initial filter와 context ranker로 Top-3를 고른다.
정답이 candidate pool 자체에 없으면 ranker가 복구할 수 없다.
따라서 v7은 "정답 후보를 pool에 넣는 능력"을 학습 대상으로 삼는다.

## 데이터 분리
- TRAIN semantic: 500
- DEV semantic: 80
- FINAL TEST: 기존 `eval/datasets/test_v1_150.jsonl`을 잠금
- `validate_dataset.py`가 locked test가 존재할 경우 normalized exact leakage를 검사한다.

## Fine-tune base model
기본값:
`gpt-4.1-mini-2025-04-14`

2026-09 기준 OpenAI 공식 fine-tuning endpoint 지원 목록에 포함된 snapshot을 사용한다.
GPT-5.6 Luna는 현재 generator/ranker baseline으로 유지하고, fine-tuned generator의 비교군으로 사용한다.

## 가장 중요한 실행 순서

### 0. 프로젝트 root에 ZIP을 병합
현재 프로젝트:
`C:\Users\User\Desktop\BCI_LLM_RESEARCH_V2`

### 1. 가상환경
```bat
.venv\Scripts\activate
```

### 2. 전체 준비
```bat
scripts\ft_1_prepare.bat
```

이 단계는 API 비용이 없다.
생성되는 리뷰 파일:
- `training\data\train_review_v1.csv`
- `training\data\dev_review_v1.csv`

**가능하면 학습 전에 CSV를 사람이 직접 확인한다.**
부자연스러운 후보는 `approved=0`으로 바꾸거나 candidates 셀에서 삭제한다.

리뷰 수정 후에는 예:
```bat
python -m training.apply_review --review training\data\train_review_v1.csv --output training\data\train_semantic_v1.jsonl
python -m training.apply_review --review training\data\dev_review_v1.csv --output training\data\dev_semantic_v1.jsonl
python -m training.validate_dataset
python -m training.export_openai_sft
python -m training.validate_openai_sft
```

### 3. 유료 학습 job 생성
```bat
scripts\ft_2_create_job.bat
```

이 BAT는 pause를 걸어두었다. 계속 진행하면 실제 Fine-tuning job이 생성되고 비용이 발생한다.

Dashboard:
https://platform.openai.com/finetune

### 4. 학습 상태 보기
```bat
scripts\ft_3_watch_job.bat
```

완료 시:
`training\artifacts\ft_model.json`

안에:
```json
{
  "status": "succeeded",
  "fine_tuned_model": "ft:gpt-4.1-mini-2025-04-14:..."
}
```

### 5. generator 자체 검증
```bat
scripts\ft_4_validate_generator.bat
```

측정:
- DEV gold candidate recall
- any-gold-hit rate
- exact initial valid rate
- latency
- Luna vs fine-tuned generator

### 6. Full pipeline DEV 비교
TEST를 먼저 열지 않는다. 이 BAT는 TRAIN 초성 그룹과 분리된 `eval/datasets/v7_pipeline_dev_20.jsonl`을 사용한다.
```bat
scripts\ft_5_dev_pipeline_benchmark.bat
```

### 7. v7 활성화 준비
`app/llm/factory_v7.py`와 `EnhancedLanguageModelClient`가 포함되어 있다.

service.py import를 안전하게 한 줄 교체:
```bat
python -m scripts.enable_v7
```

`.env`:
```env
V7_ENABLED=true
FT_GENERATOR_MODEL=ft:gpt-4.1-mini-2025-04-14:...
```

그 뒤:
```bat
python -m py_compile app\pipeline\service.py app\llm\factory_v7.py app\llm\enhanced_client.py
python -m pytest -q
python -m scripts.v7_smoke_test
```

원복:
```bat
python -m scripts.disable_v7
```

### 8. FINAL TEST는 설정을 동결한 뒤 딱 한 번
```bat
scripts\ft_6_FINAL_TEST_ONCE.bat
```

테스트를 보고 prompt/data/threshold를 다시 바꾸면 그 150개는 더 이상 final test가 아니다.
수정이 필요하면 새로운 `test_v2`를 만들어야 한다.

## v7 구조
```text
Fine-tuned generator
        ↓
phrase memory merge
        ↓
Korean exact initial filter
        ↓
context quality probe
        ↓
conditional diversity
        ↓
context ranker
        ↓
Top-3
```

## 연구에서 "학습"이라고 부를 수 있는 부분
v6.3까지는 prompt/pipeline optimization.
v7에서 `fine_tuning.jobs.create`를 실행해 model weights가 업데이트되면 이것이 실제 SFT(parameter fine-tuning) 단계다.

## 절대 하지 말 것
- `.env` / API key GitHub 업로드
- final test target을 training JSONL에 복사
- final test를 반복하면서 hyperparameter 선택
- exact initial validation을 LLM에게만 맡기기
- fine-tuned generator score를 calibrated probability라고 부르기


## QA 보강사항
- direct training scripts가 프로젝트 `.env`를 읽도록 `python-dotenv` 로딩을 추가했다.
- fine-tuned GPT-4.1-mini generator에는 GPT-5 전용일 수 있는 reasoning/verbosity 옵션을 보내지 않는다.
- TRAIN/DEV catalog exact initial 검증 완료.
- normalized duplicate 제거 완료.
- 이 대화에서 만든 locked `test_v1_150` 기준 exact normalized target leakage 0건을 확인했다.
- full-pipeline DEV는 TRAIN initial group과 분리된 20-case dataset을 사용한다.
