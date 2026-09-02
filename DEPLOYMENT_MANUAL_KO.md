# 이심전심 BCI Speller — 최종 공개 배포 매뉴얼 (Render)

## 0. 최종 배포 결정

공개 웹 데모는 **Local LoRA가 아니라 OpenAI 기반 generator + context ranker**를 사용합니다.

이유:
1. 웹 방문자가 임의의 초성/상황/문맥을 입력할 수 있어야 합니다.
2. Intel Arc/XPU/torch/LoRA 환경은 로컬 연구용으로는 의미가 있지만, 일반 CPU 웹 서비스에 그대로 올리면 이미지가 커지고 시작 시간이 길어집니다.
3. 현재 Local 0.5B LoRA는 후보 recall이 안정적이지 않았습니다.
4. OpenAI API key는 브라우저에 넣지 않고 FastAPI backend의 secret environment variable로만 보관합니다.

최종 공개 구조:

Browser `/speller`
→ FastAPI `/predict`
→ `DemoResilientLanguageModelClient`
→ OpenAI generator
→ deterministic Korean exact filter
→ OpenAI context ranker
→ Top-3
→ 웹 SSVEP 선택 시뮬레이션
→ sentence buffer / TTS

OpenAI 장애 시 발표용으로 등록된 일부 초성은 deterministic mock bank로 fallback합니다.

---

## 1. ZIP 병합

이 ZIP의 파일을 프로젝트 루트에 병합합니다.

중요:
`BCI_LLM_RESEARCH_V2/BCI_RENDER_DEPLOY_FINAL/...` 형태가 아니라
`BCI_LLM_RESEARCH_V2/app/...`, `BCI_LLM_RESEARCH_V2/render.yaml`이 되어야 합니다.

---

## 2. main.py 확인

`app/main.py`에 다음이 있어야 합니다.

```python
from app.api.speller_ui import router as speller_ui_router
```

그리고:

```python
app.include_router(speller_ui_router)
```

---

## 3. service.py 모델 factory 확인

권장:

```python
from app.llm.factory import get_language_model_client
```

이전 실험 branch가 `factory_final`을 사용해도 제공한 compatibility wrapper가 동작합니다.

---

## 4. 로컬 production-like 테스트

실제 키는 `.env` 또는 OS 환경 변수에만 둡니다.

```bat
set MOCK_MODE=false
set BCI_DEMO_MODE=true
set LOCAL_BCI_GENERATOR_ENABLED=false
set OPENAI_API_KEY=YOUR_REAL_KEY
python -m scripts.deploy_preflight
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

브라우저:

```text
http://127.0.0.1:8002/speller
```

확인:
- `/health` → 200
- `/speller` → UI 표시
- `ㅁㅈ + 목이 말라` → 후보 생성
- 임의의 초성/문맥에서도 OpenAI가 후보를 생성
- 후보 클릭 → 문장 buffer
- 문장 말하기 → 브라우저 TTS

---

## 5. 배포 직전 pytest

테스트에서는 API 비용/변동성을 제거합니다.

```bat
set MOCK_MODE=true
set BCI_DEMO_MODE=false
set LOCAL_BCI_GENERATOR_ENABLED=false
python -m pytest -q
```

통과 후 다시 실제 모드:

```bat
set MOCK_MODE=false
set BCI_DEMO_MODE=true
set LOCAL_BCI_GENERATOR_ENABLED=false
```

---

## 6. Git release branch

```bat
git checkout -b release/web-demo-v1
git status
git add .
git commit -m "release: deploy BCI speller web demo"
git push -u origin release/web-demo-v1
```

GitHub에서 PR을 열고 CI 통과 후 main에 merge합니다.

이미 main에 바로 배포할 계획이면:

```bat
git checkout main
git pull
git merge release/web-demo-v1
git push origin main
```

---

## 7. Render 배포

1. Render 계정에서 **New → Blueprint** 선택
2. GitHub의 `BCI_LLM_RESEARCH_V2` repository 연결
3. repository root의 `render.yaml`을 인식시킴
4. `OPENAI_API_KEY`는 Render dashboard에서 Secret 값으로 입력
5. Blueprint 생성

`render.yaml`의 핵심:
- Docker runtime
- Singapore region
- `/health` health check
- `BCI_DEMO_MODE=true`
- `MOCK_MODE=false`
- Local LoRA off
- generator/ranker = `gpt-5.6-luna`

Render는 배포가 끝나면 `https://<service-name>.onrender.com` 형태의 URL을 제공합니다.

최종 BCI URL:
`https://<service-name>.onrender.com/speller`

---

## 8. Render log에서 성공 기준

다음 순서가 보여야 합니다.

```text
Build successful
Deploying...
Application startup complete.
Uvicorn running on http://0.0.0.0:<PORT>
```

Render health check가 `/health`에서 성공해야 합니다.

---

## 9. 배포 후 검증

아래 URL을 각각 확인:

```text
https://<domain>/health
https://<domain>/docs
https://<domain>/speller
```

BCI 시연 4개:

### A. 기본 요구
- initials: `ㅁㅈ`
- partner: family
- situation: home
- context: `목이 말라서 물을 마시고 싶다`

### B. 감정
- initials: `ㅅㄹㅎ`
- context: `너를 너무 좋아해`

### C. 같은 초성 / 자세 문맥
- initials: `ㄷㅇㅈ`
- partner: family
- situation: positioning
- context: `혼자 자세를 바꾸기 어렵다`

### D. 같은 초성 / 일정 문맥
- initials: `ㄷㅇㅈ`
- partner: friend
- situation: schedule
- context: `다음 주에 약속 잡을까`

---

## 10. OpenAI key 보안

절대 하면 안 되는 것:
- HTML/JS에 API key 삽입
- GitHub에 `.env` 커밋
- PPT나 screenshot에 실제 key 표시
- 팀원이 하나의 개인 key를 공유

권장:
- Render secret environment variable
- 개발/배포용 프로젝트 분리
- API usage/spend alert 설정
- 유출 의심 시 즉시 rotate

---

## 11. 운영 branch 전략

권장:

```text
main
  └─ 공개 demo 안정판

develop
  └─ 다음 language pipeline 개발

experiment/*
  └─ LoRA / EEG fusion / prompt 실험

release/*
  └─ 배포 후보
```

공개 웹은 `main`만 자동 배포하도록 유지합니다.

---

## 12. Local LoRA는 삭제하지 않는다

Local LoRA는 실패한 작업이 아니라 **연구 결과**입니다.

남겨둘 것:
- Intel XPU setup
- LoRA training code
- adapter
- training history
- generator evaluation
- 실패/일반화 분석

단, 공개 demo runtime에는 포함하지 않습니다.

이렇게 해야 연구와 제품 데모를 분리할 수 있습니다.
