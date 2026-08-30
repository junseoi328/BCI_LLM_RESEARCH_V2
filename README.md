# BCI Korean Language Prediction — Research v0.2

`P300/EEG partial input → deterministic Korean validation → broad LLM generation → context ranker → EEG-language fusion → Top-K → SSVEP/UI` 연구용 백엔드입니다.

## Windows CMD 빠른 시작

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m pytest -q
python -m uvicorn app.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- 간단 테스트 UI: `http://127.0.0.1:8000/demo`
- Health: `http://127.0.0.1:8000/health`

처음에는 `.env`의 `MOCK_MODE=true`로 API 비용 없이 검증합니다.
실제 API 결제/키 설정 후 `MOCK_MODE=false`로 전환합니다.

## 실제 OpenAI 연결

`.env`:

```env
MOCK_MODE=false
OPENAI_API_KEY=YOUR_REAL_KEY
OPENAI_GENERATOR_MODEL=gpt-5.6-luna
OPENAI_RANKER_MODEL=gpt-5.6-luna
```

키는 frontend, GitHub, 로그에 넣지 않습니다.

## 첫 live 테스트

```bat
python -m scripts.live_smoke_test
```

또는 `/docs`의 `POST /predict`:

```json
{
  "input_mode": "initials",
  "bci_input": "ㄷㅇㅈ",
  "partner": "friend",
  "situation": "schedule",
  "current_sentence": "",
  "recent_context": ["다음 주에 약속 잡을까"],
  "context_level": "full",
  "top_k": 3
}
```

## 평가

50개 sanity dataset 검증:

```bat
python -m scripts.validate_dataset
```

전체 평가:

```bat
python -m eval.run_eval --context-level full
```

Context ablation:

```bat
python -m eval.run_ablation
```

모델 비교(실제 API 비용 발생):

```bat
python -m eval.run_model_benchmark --limit 20
```

결과는 `eval/reports/`에 저장됩니다.

## 핵심 설계

1. 초성 exact match는 Python/Unicode로 검증합니다.
2. Generator는 문맥 없이 10~20개의 넓은 후보를 만듭니다.
3. Ranker가 partner/situation/recent context를 기준으로 후보를 평가합니다.
4. LLM score는 확률이 아니라 ranking feature입니다.
5. 실제 EEG가 없으면 `eeg_score=None`으로 두고 language score만 사용합니다.
6. EEG가 연결되면 Top-k hypothesis를 받아 heuristic fusion합니다.
7. quota/network 문제 시 demo에서는 local fallback을 사용할 수 있습니다. 연구 평가에서는 `ALLOW_LOCAL_FALLBACK=false` 권장.
8. 모든 실제 실험은 prompt/model/pipeline/dataset version을 기록합니다.

더 자세한 실행 순서는 `README_CODE_NEXT_KO.md`를 따르세요.
