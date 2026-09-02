# Final BCI Local LoRA on Intel XPU

## 의미
이 fine-tuning은 EEG decoder가 아니라 **한국어 초성 -> 후보 생성 language generator**를 특화한다.
LoRA는 base model 전체를 다시 학습하지 않고 작은 adapter parameter를 실제로 학습한다.

최종 BCI:
P300 decoder -> 초성 -> Local fine-tuned generator -> Python exact 초성 filter
-> 기존 context-quality/Luna ranker -> Top-3 -> SSVEP -> sentence buffer

## 기존 웹사이트
기존 Swagger/Test UI는 모델 자체가 아니라 backend를 시험하는 화면이다.
`/predict` API 계약을 유지하므로 generator를 local LoRA로 바꿔도 그대로 쓸 수 있다.
추가 `/model-lab` 화면에서 학습 상태와 /predict를 같이 본다.

## 실행
XPU 설치 후:
```bat
python -m local_ft.check_xpu
```

### 1 epoch dry-run
```bat
set LOCAL_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
set LOCAL_EPOCHS=1
set LOCAL_MAX_LENGTH=384
python -m local_ft.train_lora_xpu
python -m scripts_final.local_model_smoke
python -m local_ft.evaluate_generator
```

### 학습 가시화
```bat
python -m local_ft.make_training_report
start local_models\bci_generator_lora_final\training_report.html
```

### dry-run 성공 후 최종 3 epoch
기존 `local_models\bci_generator_lora_final` 폴더를 백업/삭제한 뒤:
```bat
set LOCAL_EPOCHS=3
set LOCAL_MAX_LENGTH=512
python -m local_ft.train_lora_xpu
python -m local_ft.evaluate_generator
python -m local_ft.make_training_report
```

### FastAPI 적용
DEV 결과 확인 후:
```bat
python -m scripts_final.install_final_local
```
`app/main.py`에:
```python
from app.api.model_lab import router as model_lab_router
app.include_router(model_lab_router)
```
`.env`:
```env
LOCAL_BCI_GENERATOR_ENABLED=true
LOCAL_MODEL_DIR=local_models/bci_generator_lora_final
```
검사:
```bat
python -m py_compile app\pipeline\service.py app\llm\local_final_client.py app\llm\factory_final.py
python -m pytest -q
python -m uvicorn app.main:app --reload
```
브라우저:
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/model-lab

## 마지막 연구 단계
local generator, ranker, prompt, threshold를 freeze한 뒤 새로운 unseen final test를 한 번만 평가한다.
그 다음 박필 decoder top-k를 연결하고 실제 P300 -> language -> SSVEP end-to-end를 평가한다.
