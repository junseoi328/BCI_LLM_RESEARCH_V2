# 이심전심 — 한국어 특화 생성형 AI–EEG Hybrid BCI Speller
## 준서 파트 최종 실행 매뉴얼 v2.0 — 설계·구현·평가·통합·배포·연구 재현성

> **목적:** 이 README 하나를 처음부터 끝까지 따라가면, `P300/EEG 입력 → 한국어 입력 해석 → OpenAI 기반 후보 생성 → 초성/자모 검증 → 문맥 기반 후보 정렬 → EEG–언어 정보 결합 → Top-K 출력 → SSVEP 선택 → 문장 완성`까지 연결되는 연구용 LLM 백엔드를 구현하고, 팀 UI와 통합하고, 실험 가능한 형태로 배포하는 것을 목표로 한다.
>
> 이 문서는 단순 코딩 가이드가 아니다. **연구 설계 + 시스템 설계 + 구현 + 테스트 + 평가 + 배포 + 팀 협업 + 데이터 관리 + 최종 보고서 작성**을 모두 포함한다.
>
> 프로젝트명: **ALS 환자를 위한 한국어 특화, 문맥 기반 생성형 AI–EEG BCI Speller 개발**
>
> 준서 담당 핵심: **LLM 기반 한국어 후보 추천 및 OpenAI API 연결**

---



# 먼저 읽기 — 이번 최종판에서 다시 점검한 핵심 사항

이 문서는 이전 초안을 다시 검토한 **실행 최종판**이다. 아래 내용은 특히 혼동하기 쉬워서 명시적으로 수정·강화했다.

## A. 현재 prototype과 최종 연구 시스템을 구분한다

현재 제공된 backend prototype에는 다음이 이미 있다.

- FastAPI 서버
- `/predict`
- `/autotoggle/step`
- 초성 추출/검증
- OpenAI Structured Output 기반 후보 생성
- mock generator
- 간단한 EEG hypothesis 입력
- heuristic ranking
- toy evaluation

하지만 이것을 **최종 연구 시스템이 이미 완성된 것으로 해석하면 안 된다.** 다음은 아직 연구 단계에서 추가하거나 검증해야 한다.

- 독립적인 candidate ranker 또는 검증된 ranking 방식
- 의미 중복 제거의 정량적 기준
- 실제 P300 decoder 확률/score와의 calibration
- EEG–language fusion weight의 held-out tuning
- Auto Toggle의 실제 UI 입력 규칙과 완전한 한글 조합 정책
- Hybrid mode 전환 규칙
- 실제 React UI 통합
- 참가자 단위 experiment logging
- 개인정보/인증/접근제어
- staging/production 분리
- 실제 사용자 평가

즉 현재 코드는 **연구 플랫폼의 골격**이고, 본 매뉴얼은 그 골격을 최종 연구 결과물로 끌고 가는 절차다.

## B. LLM이 출력한 `0.91`을 확률로 부르지 않는다

LLM에게 `context_score=0.91`을 쓰게 할 수는 있지만 이는 calibrated probability가 아니다. 따라서 최종 논문/발표에서는 다음처럼 표현한다.

```text
LLM-derived relevance score
context relevance score
ranking score
```

다음 표현은 calibration 이전에는 사용하지 않는다.

```text
P(correct)=0.91
90% 확률로 정답
```

## C. 현재 heuristic fusion은 Bayesian fusion 자체가 아니다

현재 prototype의

```text
0.35 EEG + 0.35 context + 0.20 naturalness + 0.10 brevity
```

는 **초기 heuristic ranking rule**이다. 연구에서 Bayesian 관점을 설명할 수는 있지만, 실제 점수가 확률로 calibration되지 않았다면 이를 `Bayesian posterior`라고 주장하면 안 된다.

최종 연구에서는 다음 3단계를 구분한다.

1. **MVP:** heuristic weighted score
2. **Research:** validation set에서 weight/threshold 튜닝
3. **고도화:** EEG score와 language score를 calibration한 뒤 probabilistic/log-score fusion 검토

## D. EEG decoder에게 꼭 확률을 달라고 요구하되, score의 의미를 먼저 확인한다

박필에게 `top-k + score`를 받는 것이 좋다. 하지만 classifier의 `decision_function`, correlation, CCA coefficient, softmax probability는 서로 의미가 다르다. 따라서 API 필드도 초기에는 `probability`보다 아래처럼 두는 것이 안전하다.

```json
{
  "hypotheses": [
    {"input": "ㄷㅇㅈ", "decoder_score": 0.73},
    {"input": "ㄷㅇㅊ", "decoder_score": 0.19}
  ],
  "score_type": "classifier_probability"
}
```

`score_type`을 기록해야 서로 다른 decoder를 비교할 수 있다.

## E. Auto Toggle은 현재 prototype보다 실제 실험 규칙이 먼저다

현재 state machine은 `초성 → 중성 → 종성 → commit`의 기본 동작을 검증하는 수준이다. 실제 실험 전에는 반드시 팀에서 다음을 정한다.

- 복합중성 `ㅘ/ㅝ/ㅢ`를 한 선택으로 보여줄지, 두 단계로 조합할지
- 겹받침을 허용할지
- 다음 초성이 이전 음절의 종성 후보와 충돌할 때 어떻게 처리할지
- 자동 commit 시점
- backspace가 한 자모를 지울지 한 음절을 지울지
- prediction이 나타나는 시점
- SSVEP 후보를 선택하면 pending state를 어떻게 처리할지

**UI 입력 규칙을 확정한 뒤 state machine을 고친다.** 반대로 코드가 이미 그렇게 되어 있다는 이유로 실험 규칙을 코드에 맞추지 않는다.

## F. OpenAI 모델 선택은 고정 정답이 아니라 benchmark 문제다

2026-08-30 기준 OpenAI 공식 모델 가이드는 GPT-5.6 Sol을 고성능 flagship, Terra를 비용/성능 균형, Luna를 비용 민감·대량 workload로 구분한다. 이 프로젝트에서는 Luna로 MVP를 시작할 수 있지만, 최종 선택은 **같은 held-out dataset에서 정확도·latency·비용을 비교한 결과**로 결정한다.

권장 benchmark 후보:

```text
gpt-5.6-luna   : 비용 중심 baseline
gpt-5.6-terra  : 균형 후보
gpt-5.6-sol    : 품질 상한선 비교
```

## G. frontend-only 배포는 금지한다

첨부한 STROKE 앱은 Firebase를 브라우저에서 직접 읽는 정적 웹 구조지만, BCI 프로젝트에는 OpenAI secret과 잠재적으로 민감한 대화 context가 들어간다. 따라서 반드시

```text
React UI → FastAPI backend → OpenAI
```

구조로 간다.

OpenAI API key를 React/Vite 환경변수로 넣어 빌드하면 브라우저에 노출될 수 있으므로 금지한다.

## H. 연구 참가자 데이터와 개발 로그를 분리한다

개발 중 request log와 사람 대상 실험 로그는 별개다.

- 개발 로그: synthetic/test input 위주
- 참가자 로그: 익명 participant ID, trial ID, 필요한 변수만
- 실명/전화번호/환자번호/API 원문 대화 전체 저장 금지
- IRB/연구윤리 요구가 생기면 그 규칙이 이 문서보다 우선

## I. “작동”과 “연구적으로 유효”를 구분한다

```text
API가 200을 반환한다        → engineering success
Top-3가 70%를 넘는다        → offline performance
EEG와 연결되어 실시간 동작   → system integration
선택 횟수/시간이 감소한다    → research evidence
새 참가자에서도 재현된다      → external validity
```

모든 단계가 따로 필요하다.

---

# 0. 가장 먼저 읽을 것 — 이 프로젝트에서 준서가 만드는 것은 무엇인가?

준서가 만드는 것은 “ChatGPT 같은 챗봇”이 아니다.

최종적으로 만들어야 하는 것은 다음 함수에 가깝다.

```text
predict(
    EEG evidence,
    Korean partial input,
    conversation context
)
        ↓
사용자가 실제로 말하려 했을 가능성이 높은 한국어 후보 Top-K
```

전체 시스템에서의 위치는 다음과 같다.

```text
                     ┌───────────────────────┐
                     │ Conversation Context  │
                     │ 상대 / 상황 / 이전대화 │
                     └──────────┬────────────┘
                                │
                                ▼
EEG ──→ P300 Decoder ──→ Korean Input ──→ BCI Language Backend
                                │                 │
                                │                 ├─ LLM candidate generation
                                │                 ├─ Korean hard constraints
                                │                 ├─ context ranking
                                │                 ├─ EEG-language fusion
                                │                 └─ Top-K selection
                                │
                                ▼
                           Top-3 후보
                                │
                                ▼
                           SSVEP 선택
                                │
                                ▼
                           문장 Buffer
                                │
                                └────→ 다음 cycle
```

### 핵심 철학

```text
EEG가 "무엇을 선택했을 가능성이 높은가"를 제공한다.
LLM이 "언어적으로 무엇을 말하려 했을 가능성이 높은가"를 제공한다.
코드는 둘을 검증하고 결합한다.
사용자가 최종 결정을 내린다.
```

따라서 LLM이 사용자 의도를 독단적으로 결정하게 만들면 안 된다.

---

# 1. 프로젝트의 공식 성공 기준

우리 시스템이 “멋있어 보이는 것”보다 중요한 것은 **실제 communication efficiency**다.

최종 평가에서 최소 다음을 기록한다.

| 지표 | 의미 | 목표/용도 |
|---|---|---|
| Acc@1 | 정답이 1위 후보인가 | 후보 ranking 품질 |
| Acc@3 | 정답이 Top-3에 있는가 | 핵심 추천 성능 |
| MRR | 정답 순위가 얼마나 높은가 | ranking 비교 |
| BCI selection count | 문장을 완성하는 데 필요한 EEG 선택 수 | 핵심 효율성 |
| KSR | baseline 대비 선택 횟수 절감률 | 제안서 핵심 |
| Completion time | 문장 완성 시간 | 제안서 핵심 |
| Correction count | 삭제/되돌리기/재입력 수 | 오류 회복성 |
| Final success rate | 의도한 문장을 최종 완성했는가 | End-to-End 성공률 |
| LLM latency | 후보 생성 시간 | 실시간성 |
| End-to-End latency | EEG부터 후보 표시까지 시간 | 실제 UX |
| User rating | 추천 문맥 적합성/사용 편의성 | 정성 평가 |

핵심적으로 다음을 생각한다.

```text
좋은 BCI LLM ≠ 가장 긴 문장을 잘 쓰는 LLM
좋은 BCI LLM = 최소 EEG 선택으로 사용자의 의도를 정확히 찾아주는 LLM
```

---

# 2. 최종적으로 구현해야 하는 4가지 연구 조건

코드는 처음부터 다음 네 조건을 모두 켜고 끌 수 있게 설계한다.

```python
class ExperimentMode(str, Enum):
    baseline_autotoggle = "baseline_autotoggle"
    autotoggle_llm = "autotoggle_llm"
    initials_llm = "initials_llm"
    hybrid = "hybrid"
```

## A. Auto Toggle 직접 자모 입력

LLM 없음.

```text
ㄷ → ㅗ → 도
ㅇ → ㅘ → 와
ㅈ → ㅝ → 줘
```

이 조건이 baseline이 된다.

## B. Auto Toggle + LLM

부분 자모를 직접 입력하면서 적절한 시점에 LLM 후보를 보여준다.

## C. 초성열 + LLM

```text
ㄷㅇㅈ
↓
도와줘 / 들어줘 / 다음 주
```

## D. Hybrid

초성열의 중의성이 낮으면 빠른 prediction을 사용하고, 중의성이 높으면 Auto Toggle로 정보를 추가한다.

---

# 3. 시스템을 설계할 때 절대 지켜야 할 12가지 원칙

## 원칙 1. 정확히 계산할 수 있는 것은 LLM에게 맡기지 않는다

Python 담당:

- 한글 초성 추출
- 초성 exact match
- 자모 validation
- 중복 제거
- 후보 수 제한
- score 계산
- Top-K 정렬
- timeout 처리
- schema validation

LLM 담당:

- 자연스러운 후보 생성
- 문맥 이해
- 상대에게 적절한 표현 판단
- 의미적 ranking feature 생성

한 줄 요약:

```text
Deterministic problem → code
Ambiguous language problem → LLM
```

## 원칙 2. 후보 생성과 후보 ranking을 분리한다

잘못된 형태:

```text
"ㄷㅇㅈ에 해당하는 최고의 단어 3개 알려줘"
```

권장 형태:

```text
LLM → 10~20개 후보
        ↓
Python hard filter
        ↓
context ranking
        ↓
diversity filter
        ↓
Top-3
```

## 원칙 3. LLM score를 실제 확률로 해석하지 않는다

모델이 `context_score=0.93`이라고 했다고 해서 실제 정답 확률이 93%라는 뜻이 아니다.

코드와 논문에서는 처음에 다음 이름을 사용한다.

```text
context_score
language_score
rank_score
```

`probability`라는 이름은 calibration 이후에만 사용한다.

## 원칙 4. EEG decoder의 argmax 하나만 받지 않는다

나쁜 형태:

```json
{"result":"ㅈ"}
```

좋은 형태:

```json
{
  "alternatives": [
    {"symbol":"ㅈ","score":0.56},
    {"symbol":"ㅊ","score":0.27},
    {"symbol":"ㅅ","score":0.11}
  ]
}
```

## 원칙 5. 확정된 문자와 추정 중인 문자를 분리한다

```json
{
  "committed_text":"물",
  "pending_input":"ㅈ",
  "prediction_candidates":["줘","좀","주세요"]
}
```

## 원칙 6. 항상 fallback이 존재한다

```text
LLM 정상 → Top-K
LLM timeout → local fallback
후보 없음 → 더 입력
전부 실패 → 직접 자모 입력
```

LLM이 고장났다고 의사소통 전체가 중단되면 안 된다.

## 원칙 7. API Key를 frontend에 넣지 않는다

```text
React UI
   ↓
FastAPI Backend   ← OPENAI_API_KEY는 여기만
   ↓
OpenAI API
```

## 원칙 8. Demo/Mock와 Live를 분리한다

STROKE 앱의 localStorage/Firebase 이중 모드처럼, BCI 프로젝트도 반드시 다음 두 모드를 갖는다.

```text
MOCK_MODE=true
→ OpenAI 호출 없이 전체 UI/EEG integration 테스트

MOCK_MODE=false
→ 실제 OpenAI API
```

## 원칙 9. 실험 설정은 코드에 하드코딩하지 않는다

가중치, 모델, 생성 후보 수, Top-K 등을 config로 뺀다.

## 원칙 10. 모든 실험은 version을 기록한다

```text
model_version
prompt_version
pipeline_version
dataset_version
frontend_version
```

## 원칙 11. 연구용 로그와 민감 데이터는 분리한다

실명, 병원 번호, 연락처가 없어도 연구 평가는 가능하도록 설계한다.

## 원칙 12. 실험 전에 offline eval부터 통과한다

실제 EEG 사람 실험에서 prompt tuning을 하지 않는다.

먼저 고정 데이터셋에서 비교하고, 결정된 버전만 사람 실험에 사용한다.

---

# 4. 권장 기술 스택

## Backend

```text
Python 3.11+
FastAPI
Pydantic
OpenAI Python SDK
Uvicorn
pytest
```

## Frontend

프로젝트 제안서의 방향에 맞추면:

```text
React
Vite
TypeScript 권장
```

TypeScript를 사용할 수 없다면 JavaScript도 가능하다.

## Research / analysis

```text
pandas
numpy
scipy
matplotlib
scikit-learn
```

## Version control

```text
Git
GitHub Private Repository
```

## Deployment

Prototype:

```text
Frontend: Vercel / Firebase Hosting / Netlify
Backend: Render / Railway / Fly.io
```

장기적으로는 학교/연구실 서버 또는 AWS/GCP 등을 검토한다.

---

# 5. 권장 Repository 구조

STROKE 앱처럼 기능별 파일 책임을 명확히 나눈다.

```text
isimjeonsim-bci/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   │
│   │   ├── api/
│   │   │   ├── predict.py
│   │   │   ├── autotoggle.py
│   │   │   ├── session.py
│   │   │   └── health.py
│   │   │
│   │   ├── korean/
│   │   │   ├── initials.py
│   │   │   ├── jamo.py
│   │   │   └── composer.py
│   │   │
│   │   ├── context/
│   │   │   ├── manager.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── openai_client.py
│   │   │   ├── mock_client.py
│   │   │   ├── prompts.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── pipeline/
│   │   │   ├── normalize.py
│   │   │   ├── generate.py
│   │   │   ├── filter.py
│   │   │   ├── rank.py
│   │   │   ├── diversity.py
│   │   │   ├── fusion.py
│   │   │   ├── fallback.py
│   │   │   └── service.py
│   │   │
│   │   ├── sessions/
│   │   │   └── manager.py
│   │   │
│   │   └── logging/
│   │       └── experiment_logger.py
│   │
│   ├── tests/
│   │   ├── test_initials.py
│   │   ├── test_autotoggle.py
│   │   ├── test_filter.py
│   │   ├── test_rank.py
│   │   └── test_api.py
│   │
│   ├── eval/
│   │   ├── datasets/
│   │   │   ├── dev_v1.jsonl
│   │   │   └── test_v1.jsonl
│   │   ├── evaluate.py
│   │   ├── metrics.py
│   │   └── reports/
│   │
│   ├── .env.example
│   ├── .gitignore
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── screens/
│   │   ├── hooks/
│   │   ├── state/
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── README.md
│
├── shared/
│   ├── api_contract.md
│   └── experiment_modes.md
│
├── research/
│   ├── papers/
│   ├── protocol/
│   ├── results/
│   └── figures/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── EXPERIMENT.md
│   ├── SECURITY.md
│   └── CHANGELOG.md
│
├── TODO.md
└── README.md
```

### 파일 분리 원칙

한 파일에 다음을 모두 넣지 않는다.

```text
API
OpenAI
한글 처리
ranking
experiment logging
```

기능 하나가 고장났을 때 어느 파일을 봐야 하는지가 명확해야 한다.

---

# 6. GitHub 저장소를 만드는 방법

## 저장소

반드시 **Private Repository**로 시작한다.

```text
isimjeonsim-bci
```

## 최초 설정

```bash
git init
git add .
git commit -m "chore: initialize BCI project"
git branch -M main
git remote add origin <PRIVATE_GITHUB_REPO>
git push -u origin main
```

## Branch 규칙

```text
main
└─ 안정/통합 버전

dev
└─ 다음 통합 버전

feature/*
└─ 개인 개발
```

예:

```text
feature/llm-ranking
feature/eeg-api
feature/autotoggle
feature/ssvep-ui
```

## 반드시 지킬 팀 규칙

STROKE 개발 방식의 장점을 그대로 가져온다.

1. 작업 시작 전 `git pull`.
2. 같은 파일을 두 명이 동시에 크게 수정하지 않는다.
3. 한 commit은 한 목적만 가진다.
4. 직접 `main`에 실험 코드 push하지 않는다.
5. 통합 전 preview/test를 한다.
6. 배포 권한자는 초기에는 1명으로 제한한다.

### 좋은 commit

```text
feat: add Korean initial extraction
fix: reject duplicated LLM candidates
feat: add EEG top-k hypothesis schema
test: add Auto Toggle composition cases
refactor: separate ranking from candidate generation
```

### 나쁜 commit

```text
수정
asdf
finalfinal
진짜최종
```

---

# 7. `.gitignore`

최소 다음을 넣는다.

```gitignore
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.venv/

# Secret
.env
.env.*
!.env.example

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Research data containing participant-level records
data/private/
logs/private/

# Generated
*.log
coverage/
```

**절대 GitHub에 올리면 안 되는 것:**

```text
OPENAI_API_KEY
참가자 실명
연락처
병원/환자 식별 정보
원본 민감 대화 기록
개인 API 키
```

---

# 8. Backend 최초 실행

```bash
cd backend
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

설치:

```bash
pip install -r requirements.txt
```

권장 `requirements.txt`:

```text
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
openai>=1.100,<3
pydantic>=2.8,<3
python-dotenv>=1.0,<2
pytest>=8,<10
httpx>=0.27,<1
pandas>=2,<3
numpy>=2,<3
```

서버:

```bash
uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 9. 환경변수 설계

`.env.example`:

```env
# Runtime
APP_ENV=development
DEBUG_MODE=false
MOCK_MODE=true

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=low

# Candidate pipeline
GENERATION_COUNT=12
DISPLAY_TOP_K=3

# Ranking
WEIGHT_EEG=0.35
WEIGHT_CONTEXT=0.35
WEIGHT_NATURALNESS=0.20
WEIGHT_BREVITY=0.10

# Timeout
OPENAI_TIMEOUT_SEC=3.0

# Frontend
ALLOWED_ORIGINS=http://localhost:5173

# Version
PIPELINE_VERSION=0.1.0
PROMPT_VERSION=gen-v1
```

### 모델 선택

현재 OpenAI GPT-5.6 계열 기준으로 초기 연구에서는 다음 전략이 합리적이다.

```text
gpt-5.6-luna
→ 비용/대량 실험에 유리한 기본 후보

gpt-5.6-terra
→ Luna 성능이 부족할 때 비교 모델

gpt-5.6-sol
→ quality ceiling 실험용
```

**중요:** 모델은 감으로 고르지 않는다. 동일 test set에서 `정확도 / latency / cost`를 비교한다.

---

# 10. API Contract를 코딩보다 먼저 확정한다

팀 통합에서 가장 중요한 문서다.

## `POST /predict`

### Request

```json
{
  "session_id": "S001",
  "trial_id": "T017",
  "experiment_mode": "initials_llm",
  "input_mode": "initials",
  "bci_input": "ㄷㅇㅈ",
  "partner": "family",
  "situation": "positioning",
  "current_sentence": "",
  "recent_context": [
    "자세 괜찮아?"
  ],
  "eeg_hypotheses": [
    {"input": "ㄷㅇㅈ", "score": 0.61},
    {"input": "ㄷㅇㅊ", "score": 0.22},
    {"input": "ㅌㅇㅈ", "score": 0.17}
  ],
  "top_k": 3
}
```

### Response

```json
{
  "request_id": "req_abc123",
  "candidates": [
    {
      "candidate_id": "c1",
      "text": "도와줘",
      "rank": 1,
      "matched_input": "ㄷㅇㅈ",
      "eeg_score": 0.61,
      "context_score": 0.91,
      "naturalness_score": 0.92,
      "final_score": 0.81
    },
    {
      "candidate_id": "c2",
      "text": "들어줘",
      "rank": 2,
      "matched_input": "ㄷㅇㅈ",
      "eeg_score": 0.61,
      "context_score": 0.62,
      "naturalness_score": 0.87,
      "final_score": 0.69
    },
    {
      "candidate_id": "c3",
      "text": "다음 주",
      "rank": 3,
      "matched_input": "ㄷㅇㅈ",
      "eeg_score": 0.61,
      "context_score": 0.31,
      "naturalness_score": 0.90,
      "final_score": 0.59
    }
  ],
  "fallback": "none",
  "latency_ms": 480,
  "model": "gpt-5.6-luna",
  "pipeline_version": "0.1.0",
  "prompt_version": "gen-v1"
}
```

### UI가 알아야 하는 것은 이것뿐이다

```text
candidates[].candidate_id
candidates[].text
candidates[].rank
fallback
```

UI가 OpenAI 내부 구조나 prompt를 알 필요가 없게 한다.

---

# 11. Pydantic Schema

```python
from enum import Enum
from pydantic import BaseModel, Field

class InputMode(str, Enum):
    initials = "initials"
    jamo = "jamo"

class Partner(str, Enum):
    family = "family"
    caregiver = "caregiver"
    medical_staff = "medical_staff"
    friend = "friend"
    other = "other"

class Situation(str, Enum):
    general = "general"
    home = "home"
    hospital = "hospital"
    meal = "meal"
    pain = "pain"
    positioning = "positioning"
    emergency = "emergency"

class EEGHypothesis(BaseModel):
    input: str
    score: float = Field(ge=0, le=1)

class PredictionRequest(BaseModel):
    session_id: str | None = None
    trial_id: str | None = None
    input_mode: InputMode
    bci_input: str
    partner: Partner = Partner.other
    situation: Situation = Situation.general
    current_sentence: str = ""
    recent_context: list[str] = []
    eeg_hypotheses: list[EEGHypothesis] | None = None
    top_k: int = Field(default=3, ge=1, le=5)
```

### Schema의 역할

잘못된 입력을 pipeline 내부로 보내지 않는 것이다.

```text
top_k = -100
score = 5
bci_input = ""
```

같은 값은 API 입구에서 막는다.

---

# 12. 한국어 초성 처리 모듈

## 초성 목록

```python
CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ",
    "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ",
    "ㅋ", "ㅌ", "ㅍ", "ㅎ"
]
```

한글 완성형의 Unicode 구조:

```text
19 초성 × 21 중성 × 28 종성
```

초성 하나당:

```text
21 × 28 = 588
```

따라서:

```python
def get_initial(ch: str) -> str | None:
    code = ord(ch) - ord("가")
    if code < 0 or code >= 19 * 21 * 28:
        return None
    return CHO[code // 588]
```

## 공백은 무시

```python
extract_initials("도와줘")       # ㄷㅇㅈ
extract_initials("물 줘")        # ㅁㅈ
extract_initials("자세 바꿔줘")  # ㅈㅅㅂㄲㅈ
```

## Unit Test

```python
def test_initials():
    assert extract_initials("도와줘") == "ㄷㅇㅈ"
    assert extract_initials("물 줘") == "ㅁㅈ"
    assert exact_initial_match("도와줘", "ㄷㅇㅈ")
    assert not exact_initial_match("도와주세요", "ㄷㅇㅈ")
```

---

# 13. Input Normalizer

Raw EEG/UI 입력은 반드시 normalize한다.

```text
" ㄷ ㅇ ㅈ "
"ㄷㅇ ㅈ"
"ㄷㅇㅈ"
```

모두:

```text
ㄷㅇㅈ
```

로 만든다.

검사:

- Unicode normalization
- whitespace 제거
- 허용된 자모인지
- 길이 제한
- mode와 입력이 일치하는지

초성열 mode에서 `ㄷㅗ`가 들어오면 reject한다.

---

# 14. Auto Toggle 한글 조합 State Machine

Auto Toggle은 prompt가 아니라 application state다.

## 상태

```text
EMPTY
INITIAL_SELECTED
MEDIAL_SELECTED
SYLLABLE_READY
COMMITTED
CORRECTION
```

## 예

```text
EMPTY
 ↓ ㄷ
INITIAL_SELECTED("ㄷ")
 ↓ ㅗ
SYLLABLE_READY("도")
 ↓ commit
COMMITTED("도")
```

종성이 있으면:

```text
ㅁ → ㅜ → ㄹ
↓
물
```

## State Schema

```python
class AutoToggleState(BaseModel):
    committed_text: str = ""
    initial: str | None = None
    medial: str | None = None
    final: str | None = None
```

## Action

```text
input
commit
backspace
reset
undo
```

## 반드시 테스트할 케이스

```text
ㄷ + ㅗ = 도
ㅁ + ㅜ + ㄹ = 물
backspace after medial
backspace after final
reset
commit 후 다음 음절
잘못된 자모 순서
```

---

# 15. Context Manager

LLM에게 전체 대화를 무작정 다 보내지 않는다.

Context를 계층화한다.

```text
Level 1: Global
- language=ko

Level 2: Partner
- family
- caregiver
- medical_staff
- friend

Level 3: Situation
- general
- meal
- pain
- positioning
- hospital

Level 4: Current sentence
- 지금 작성 중인 문장

Level 5: Recent context
- 최근 2~5개 발화

Level 6: Optional user preference
- 자주 쓰는 말투/표현
```

## 예

```json
{
  "partner":"family",
  "situation":"positioning",
  "current_sentence":"",
  "recent_context":[
    "자세 괜찮아?"
  ]
}
```

## 제한

- 최근 대화 최대 5개부터 시작
- 발화당 길이 제한
- 민감정보 제거
- 오래된 대화는 summary로 축약

---

# 16. OpenAI Candidate Generator

LLM은 일단 **후보 생성기**다.

## System/Developer Instruction의 목적

```text
- 한국어 communication candidate 생성
- 입력 초성/자모를 최대한 준수
- context를 이용
- 동일 의미 반복 금지
- 짧고 실제 선택 가능한 표현 우선
- 의료적 진단 생성 금지
- ALS라는 이유로 모든 표현을 의료 상황으로 편향하지 않기
```

## 권장 Prompt

```text
너는 한국어 BCI 의사소통 시스템의 후보 생성기다.

목표:
사용자가 BCI를 통해 입력한 부분적 한글 정보와 현재 대화 문맥을 이용하여
사용자가 실제로 말하려 했을 가능성이 높은 짧고 자연스러운 후보를 생성한다.

규칙:
1. 사용자의 질환을 근거로 의도를 임의 추정하지 않는다.
2. 제공된 입력과 문맥을 우선한다.
3. 같은 의미의 후보를 여러 번 만들지 않는다.
4. 실제 의사소통에서 바로 선택 가능한 짧은 표현을 우선한다.
5. 의료진 상대에서는 필요할 경우 자연스러운 존댓말을 사용한다.
6. 의학적 진단/치료 판단을 새로 생성하지 않는다.
7. 설명문 없이 구조화된 후보만 반환한다.
```

Input:

```text
INPUT_MODE: initials
BCI_INPUT: ㄷㅇㅈ
PARTNER: family
SITUATION: positioning
CURRENT_SENTENCE:
RECENT_CONTEXT:
- 자세 괜찮아?

서로 의미가 가능한 한 겹치지 않는 후보를 12개 생성하라.
```

---

# 17. Structured Outputs

자유 텍스트 응답을 parsing하지 않는다.

나쁜 출력:

```text
제가 추천하는 단어는 다음과 같습니다...
```

원하는 출력:

```json
{
  "candidates": [
    {
      "text":"도와줘",
      "context_score":0.92,
      "naturalness_score":0.91,
      "brevity_score":0.88
    }
  ]
}
```

Pydantic으로 다시 validation한다.

### 반드시 검증

```text
text 비어 있음?
score 범위 0~1?
candidates array인가?
필요한 key가 모두 존재하는가?
```

---

# 18. 후보 생성 수와 표시 수를 분리

환경변수 예:

```text
GENERATION_COUNT=12
DISPLAY_TOP_K=3
```

Pipeline:

```text
12 generated
↓
9 Korean-valid
↓
7 unique
↓
6 context-valid
↓
Top-3 displayed
```

왜 필요한가?

LLM이 3개 중 하나를 규칙에 맞지 않게 생성했을 때 바로 후보 부족이 되지 않도록 한다.

---

# 19. Hard Filter

초성열 mode의 가장 중요한 hard constraint:

```python
if extract_initials(candidate.text) != input_initials:
    reject(candidate)
```

예:

```text
입력: ㄷㅇㅈ

도와줘       ㄷㅇㅈ       PASS
들어줘       ㄷㅇㅈ       PASS
도와주세요   ㄷㅇㅈㅅㅇ   FAIL
```

또한:

- 빈 문자열 reject
- 길이 초과 reject
- canonical duplicate reject
- 위험한 control character reject

---

# 20. Candidate Deduplication

문자열 중복:

```text
"물 줘"
"물줘"
```

canonicalize 후 같으면 하나만 남긴다.

```python
import re

def canonicalize(text: str):
    return re.sub(r"[\s\W_]+", "", text).lower()
```

## Semantic duplicate

다음은 문자열은 다르지만 의미상 너무 유사하다.

```text
도와줘
도와주세요
좀 도와줘
```

초기 버전:

- exact/canonical duplicate만 제거
- ranker prompt에서 diversity 지시

후기 버전:

- embedding similarity
- semantic clustering

을 연구한다.

---

# 21. Ranking

초기 heuristic:

```text
FinalScore =
0.35 × EEG
+ 0.35 × Context
+ 0.20 × Naturalness
+ 0.10 × Brevity
```

**절대 이 weight를 연구 결과처럼 주장하지 않는다.**

초기 시스템을 움직이기 위한 출발점일 뿐이다.

## 다음 단계

validation dataset에서:

```text
WEIGHT_EEG = 0.0, 0.1, ... 1.0
```

grid search를 한다.

---

# 22. EEG–Language Fusion

연구적으로 가장 중요한 구조다.

목표:

```text
P(W | E, C)
```

- W: intended utterance
- E: EEG evidence
- C: conversation context

개념적으로:

```text
P(W | E, C) ∝ P(E | W) × P(W | C)
```

로그 영역:

```text
score(W)
= λ log EEG_score(W)
+ (1-λ) language_score(W|C)
```

## 중요한 주의

현재 EEG classifier score와 LLM score가 calibrated probability가 아닐 수 있다.

그러므로 초기에는 **Bayesian interpretation을 가진 heuristic fusion**이라고 정확히 표현한다.

후속 연구에서 calibration을 한다.

---

# 23. 오입력 보정

“LLM이 입력을 마음대로 고치는 시스템”을 만들면 안 된다.

대신:

```text
EEG uncertainty expansion
→ language-based reranking
```

으로 설계한다.

예:

```text
Position 3 EEG:
ㅈ 0.48
ㅊ 0.42
ㅅ 0.10
```

이면:

```text
ㄷㅇㅈ
ㄷㅇㅊ
ㄷㅇㅅ
```

에 대해 후보를 생성한 후 최종 ranking한다.

반대로:

```text
ㅊ 0.98
ㅈ 0.01
```

이면 LLM 문맥만으로 강제로 `ㅈ`로 바꾸지 않는다.

---

# 24. Top-K와 Fallback

최종 UI에서 추천 후보만 보여주면 안 된다.

권장:

```text
후보 1
후보 2
후보 3
다른 후보 / 더 입력 / 뒤로
```

API `fallback` 값 예:

```text
none
more_input
more_candidates
reinput
llm_timeout
local_fallback
```

---

# 25. Session State

LLM conversation memory만 믿지 말고 application state를 명시적으로 관리한다.

예:

```json
{
  "session_id":"S001",
  "committed_text":"물 줘",
  "pending_input":"",
  "partner":"family",
  "situation":"home",
  "recent_context":[...],
  "last_candidate_ids":["c1","c2","c3"]
}
```

이점:

- 재현성
- 디버깅
- undo
- 실험 조건 통제
- 개인정보 최소화

---

# 26. Backend Endpoint 목록

최소:

```text
GET  /health
POST /predict
POST /autotoggle/step
POST /session/create
POST /session/commit
POST /session/undo
POST /session/reset
```

연구용 선택:

```text
POST /experiment/trial/start
POST /experiment/trial/end
```

## `/health`

```json
{
  "status":"healthy",
  "version":"0.1.0",
  "mock_mode":true
}
```

---

# 27. FastAPI Main

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Korean BCI Language API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

개발 초기에 `allow_origins=["*"]`를 쓸 수 있지만 public deployment 전에는 실제 frontend 주소로 제한한다.

---

# 28. Mock Mode

Mock generator 예:

```python
MOCK_BANK = {
    "ㄷㅇㅈ": ["도와줘", "들어줘", "다음 주"],
    "ㅁㅈ": ["물 줘", "뭐지", "맞지"],
    "ㅂㄲㅈ": ["불 꺼줘"],
}
```

이것의 목적은 성능을 주장하는 것이 아니다.

다음 통합을 OpenAI/EEG 없이 테스트하기 위해서다.

```text
Frontend ↔ Backend
P300 simulator ↔ Backend
SSVEP screen ↔ candidate response
```

---

# 29. Frontend 구조

React라면:

```text
frontend/src/
│
├── api/
│   └── bciApi.ts
├── types/
│   └── api.ts
├── components/
│   ├── PartnerSelector.tsx
│   ├── P300Keyboard.tsx
│   ├── CandidateGrid.tsx
│   ├── SentenceBuffer.tsx
│   ├── CorrectionBar.tsx
│   └── StatusIndicator.tsx
├── screens/
│   ├── StartScreen.tsx
│   ├── PartnerScreen.tsx
│   ├── InputScreen.tsx
│   └── CompletedScreen.tsx
├── state/
│   └── sessionStore.ts
└── App.tsx
```

### 준서가 frontend를 전부 만들 필요는 없다

하지만 반드시 API를 직접 호출하는 작은 test UI 하나는 만들어볼 수 있어야 한다.

---

# 30. Frontend API Client

```ts
export async function predict(request: PredictionRequest) {
  const res = await fetch(`${API_BASE}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    throw new Error(`predict failed: ${res.status}`);
  }

  return await res.json();
}
```

UI에서 직접 OpenAI를 부르면 안 된다.

---

# 31. 추천 후보 UI 규칙

SSVEP 후보라면 다음을 가빈과 확정한다.

- 표시 후보 수
- 후보 영역 크기
- 글자 길이 제한
- 동일 의미 후보 금지
- “다른 후보” 위치
- 삭제/되돌리기 위치
- SSVEP frequency mapping
- timeout 화면
- loading 화면

준서 API는 후보의 텍스트 외에 `candidate_id`를 반드시 제공한다.

그래야 선택 로그를 안정적으로 연결할 수 있다.

---

# 32. EEG 팀과 확정해야 할 Contract

박필에게 다음 format을 요청한다.

```json
{
  "trial_id":"P300_0041",
  "timestamp":1725000000,
  "hypotheses":[
    {"input":"ㄷㅇㅈ","score":0.61},
    {"input":"ㄷㅇㅊ","score":0.22},
    {"input":"ㅌㅇㅈ","score":0.17}
  ],
  "decoder_latency_ms":385
}
```

준서가 확인할 질문:

1. score가 softmax probability인가?
2. calibrated되어 있는가?
3. top-k 몇 개까지 안정적으로 제공 가능한가?
4. 각 position별 probability인가, 전체 sequence score인가?
5. P300 한 선택의 평균 latency는?
6. 오류가 났을 때 decoder가 unknown을 줄 수 있는가?

---

# 33. Evaluation Dataset 설계

LLM 연구에서 가장 먼저 필요한 자산 중 하나다.

## 최소 schema

```json
{
  "id":"case_001",
  "target":"도와줘",
  "initials":"ㄷㅇㅈ",
  "auto_toggle":["ㄷ","ㅗ","ㅇ","ㅘ","ㅈ","ㅝ"],
  "partner":"family",
  "situation":"positioning",
  "current_sentence":"",
  "recent_context":["자세 괜찮아?"],
  "category":"physical_request"
}
```

## 추천 category

```text
basic_request
positioning
pain
meal
environment
calling_person
general_conversation
emotion
question
social_expression
medical_communication
```

**의료 문장만 만들지 않는다.**

일상 대화도 충분히 포함한다.

---

# 34. Dataset Split

예: 300개

```text
Dev: 240
Held-out Test: 60
```

Dev:

- prompt 수정
- weight 조정
- pipeline 수정

Test:

- 최종 비교 때만 사용

Test를 보면서 prompt를 계속 수정하면 test가 test가 아니게 된다.

---

# 35. 평가 함수

## Acc@1

```text
정답이 1위 / 전체
```

## Acc@3

```text
정답이 Top-3 안 / 전체
```

## MRR

```text
MRR = average(1 / target_rank)
```

예:

```text
rank 1 → 1.0
rank 2 → 0.5
rank 3 → 0.333
없음 → 0
```

## KSR

```text
KSR = 1 - system_selection / baseline_selection
```

---

# 36. 연구 Ablation

반드시 다음 비교를 실행한다.

```text
A0. initials only
A1. initials + partner
A2. initials + partner + situation
A3. initials + recent context
A4. initials + full context
A5. initials + full context + EEG Top-k
```

결과표:

| Condition | Acc@1 | Acc@3 | MRR | latency |
|---|---:|---:|---:|---:|
| initials | | | | |
| + partner | | | | |
| + situation | | | | |
| + context | | | | |
| + EEG | | | | |

이 표가 있으면 “문맥이 실제로 도움이 됐다”는 주장을 데이터로 할 수 있다.

---

# 37. Model Benchmark

동일한 test set으로:

```text
gpt-5.6-luna
gpt-5.6-terra
gpt-5.6-sol
```

을 비교할 수 있다.

표:

| Model | Acc@3 | Latency | Cost/request |
|---|---:|---:|---:|
| Luna | | | |
| Terra | | | |
| Sol | | | |

연구용 실시간 서비스에서는 최고 accuracy가 아니라 **Pareto optimum**을 찾는다.

---

# 38. Prompt Versioning

```text
prompts/
├── generator_v1.txt
├── generator_v2.txt
├── ranker_v1.txt
└── CHANGELOG.md
```

로그:

```json
{
  "prompt_version":"generator_v3"
}
```

좋은 prompt 변경 기록:

```text
v1: initials + context basic
v2: duplicate diversity instruction 추가
v3: medical overprediction 억제
v4: current_sentence 강조
```

---

# 39. Logging

연구용으로 다음을 기록한다.

```json
{
  "timestamp":"...",
  "session_id":"S001",
  "trial_id":"T020",
  "mode":"initials_llm",
  "input":"ㄷㅇㅈ",
  "target":"도와줘",
  "generated_count":12,
  "valid_count":7,
  "final_candidates":["도와줘","들어줘","다음 주"],
  "target_rank":1,
  "selected_candidate_id":"c1",
  "llm_latency_ms":410,
  "pipeline_latency_ms":425,
  "decoder_latency_ms":370,
  "correction_count":0,
  "model":"gpt-5.6-luna",
  "prompt_version":"gen-v3",
  "pipeline_version":"0.4.0"
}
```

### 절대 로그에 넣지 말 것

- 실명
- 전화번호
- 환자번호
- 병원 식별 정보
- API Key

---

# 40. Failure Taxonomy

오답을 그냥 “틀림”으로 기록하지 않는다.

```text
E01_INITIAL_MISMATCH
E02_NO_VALID_CANDIDATE
E03_CONTEXT_MISS
E04_SEMANTIC_DUPLICATE
E05_POLITENESS_MISMATCH
E06_OVER_COMPLETION
E07_LLM_TIMEOUT
E08_SCHEMA_ERROR
E09_EEG_AMBIGUITY
E10_USER_REJECTED_ALL
E11_AUTOTOGGLE_STATE_ERROR
E12_NETWORK_ERROR
```

이후 결과에서:

```text
E03가 42%
```

라면 prompt/context 설계를 개선해야 한다는 것이 보인다.

---

# 41. Backend Error Handling

STROKE TODO에서 특히 좋은 교훈은 **저장/네트워크 실패가 조용히 넘어가면 안 된다**는 것이다.

BCI에서도 모든 외부 호출을 명시적으로 처리한다.

```python
try:
    result = generator.generate(...)
except TimeoutError:
    return local_fallback(...)
except Exception as exc:
    logger.exception(exc)
    return safe_reinput_response()
```

Frontend에는:

```text
후보 생성 중…
연결이 불안정합니다
다시 입력
직접 입력으로 계속
```

같은 상태가 있어야 한다.

**빈 회색 화면 금지.**

---

# 42. Retry 정책

무한 retry 금지.

예:

```text
OpenAI request
↓ failure
1회 retry
↓ failure
local fallback/reinput
```

BCI에서는 5초를 더 기다리는 것이 잘못된 후보보다 더 나쁠 수도 있다.

---

# 43. Latency Budget

각 단계 시간을 기록한다.

```text
T_total =
T_EEG
+ T_backend_preprocess
+ T_LLM
+ T_postprocess
+ T_network
+ T_UI
```

예:

```text
P300 decoding: 1200 ms
backend: 5 ms
OpenAI: 420 ms
ranking: 2 ms
network: 50 ms
UI: 30 ms
```

이렇게 해야 LLM이 문장 완성 시간을 실제로 줄이는지 판단할 수 있다.

---

# 44. Test 전략

## Unit tests

- 초성 extraction
- input validation
- Auto Toggle composition
- duplicate removal
- ranking score
- fallback

## Integration tests

```text
Mock generator → pipeline → API
```

## Live API tests

별도 mark:

```bash
pytest -m live
```

기본 CI에서는 실제 API 비용이 들지 않게 한다.

## Frontend integration

Mock backend로 먼저 한다.

---

# 45. 최소 테스트 목록

```text
[ ] ㄷㅇㅈ → exact candidates만 남는가
[ ] 공백 입력 normalize 되는가
[ ] ㄷㅗ가 initials mode에서 reject 되는가
[ ] duplicate 제거되는가
[ ] LLM이 이상한 JSON을 보내도 깨지지 않는가
[ ] API timeout fallback 되는가
[ ] Top-3 부족 시 fallback이 표시되는가
[ ] EEG hypotheses 순서가 달라도 score ranking이 정상인가
[ ] Auto Toggle backspace가 정상인가
[ ] session reset 후 이전 문장이 남지 않는가
```

---

# 46. TODO 우선순위 — STROKE 스타일 적용

## A 등급 — 이것 없으면 연구/통합 불가

- [ ] `/predict` request/response contract 확정
- [ ] Korean initials exact validator
- [ ] Mock mode
- [ ] OpenAI Structured Output 호출
- [ ] Top-K hard filter/ranking
- [ ] Auto Toggle state machine
- [ ] API key server-only
- [ ] timeout/fallback
- [ ] unit tests
- [ ] experiment logging 기본
- [ ] UI와 `/predict` mock integration

## B 등급 — 첫 pilot 전에 완료

- [ ] EEG Top-k hypothesis 연동
- [ ] context manager
- [ ] semantic duplicate 완화
- [ ] Acc@1/3/MRR evaluator
- [ ] dev/test dataset 분리
- [ ] prompt version 관리
- [ ] pipeline version 관리
- [ ] latency breakdown
- [ ] preview deployment
- [ ] real API integration test

## C 등급 — 본 실험 전/후 고도화

- [ ] calibrated confidence
- [ ] adaptive Hybrid switching
- [ ] local language fallback model
- [ ] personalization
- [ ] embedding diversity
- [ ] advanced language prior fusion
- [ ] automatic report generation

---

# 47. 보안 및 개인정보

이 프로젝트는 의료/보조의사소통 맥락을 가진다. 따라서 STROKE 앱보다 보안 기준을 훨씬 높여야 한다.

## 금지

```text
Frontend에 OpenAI Key
GitHub에 .env
실명과 대화 전체를 그대로 API로 전송
연구 로그에 식별 가능한 환자 정보
공개 Firestore rules
```

## 원칙

- 최소 정보만 외부 API로 보낸다.
- 실험용 participant ID는 random/pseudonymous ID 사용.
- 로그에서 API payload와 사용자 식별 데이터를 분리.
- 실제 환자 연구 전에는 연구윤리/IRB 여부를 반드시 확인.
- 의료적 진단/치료 추천 기능으로 확장하지 않는다.

---

# 48. OpenAI 비용 관리

비용 자체보다 중요한 것은 **호출 횟수와 token을 로그로 관리**하는 것이다.

저장:

```text
request_count
input_tokens
output_tokens
model
estimated_cost
```

개발 중에는:

```text
MOCK_MODE=true
```

를 기본으로 한다.

실제 API를 쓰는 경우도 evaluation batch를 계획적으로 실행한다.

---

# 49. Prompt 길이 관리

고정 instruction은 앞에 둔다.

```text
[Stable]
Role
Rules
Schema intent

[Dynamic]
Partner
Situation
Current sentence
Recent context
BCI input
```

최근 대화를 무제한으로 보내지 않는다.

---

# 50. Frontend 배포와 Backend 배포 분리

STROKE는 Firebase Hosting에 정적 파일 전체를 올리는 구조지만, 이 프로젝트에는 OpenAI secret이 있기 때문에 frontend-only 구조로 만들면 안 된다.

권장:

```text
Frontend
Vercel/Firebase Hosting

Backend
Render/Railway/Fly.io
```

### 환경변수

Backend deployment console에서:

```text
OPENAI_API_KEY
OPENAI_MODEL
ALLOWED_ORIGINS
```

를 설정한다.

---

# 51. Preview → Production 배포 규칙

STROKE README에서 가장 가져올 가치가 큰 습관이다.

```text
Local
↓
Preview/Staging
↓
Team integration test
↓
Production
```

절대:

```text
코드 수정 → 바로 실험용 운영 서버
```

으로 가지 않는다.

## 환경 이름

```text
local
staging
production
```

---

# 52. Docker

Backend `Dockerfile` 예:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Docker는 개발 초기에 필수는 아니지만 배포 재현성을 높인다.

---

# 53. Health Check

배포 후 확인:

```bash
curl https://<backend>/health
```

정상:

```json
{"status":"healthy"}
```

Frontend는 주기적으로 health를 보여줄 필요는 없지만 실험 운영자가 쉽게 확인할 수 있어야 한다.

---

# 54. README 운영 규칙

STROKE 프로젝트처럼 README가 실제 운영자 매뉴얼 역할을 해야 한다.

코드 변경 후 다음 중 하나가 바뀌면 README도 함께 수정한다.

```text
실행 방법
환경변수
API schema
배포 명령
file structure
실험 조건
model
fallback
보안 규칙
```

README가 코드와 다르면 README가 없는 것보다 더 위험하다.

---

# 55. 팀별 Interface 체크리스트

## 혜연에게 받을 것

- [ ] P300 stimulus layout
- [ ] 한 selection의 평균 시간
- [ ] 사용 가능한 자모 set
- [ ] SSVEP 후보 수
- [ ] 주파수 mapping
- [ ] SSVEP 평균 선택 시간
- [ ] 실험 trial 시작/종료 이벤트 정의

## 박필에게 받을 것

- [ ] decoder output JSON
- [ ] top-k hypotheses
- [ ] score 의미
- [ ] decoder latency
- [ ] unknown/low-confidence 처리
- [ ] trial_id
- [ ] SSVEP decoded candidate id

## 가빈에게 줄 것

- [ ] `/predict` request schema
- [ ] `/predict` response schema
- [ ] candidate_id
- [ ] loading/error/fallback state
- [ ] top_k
- [ ] undo/delete API 또는 state 규칙
- [ ] mock server 주소

---



# 55.5. 반드시 사용하는 Stage-Gate 방식

각 단계는 “대충 됨”으로 넘어가지 말고 아래 통과 조건을 만족한 뒤 다음 단계로 간다.

| Gate | 통과 조건 | 실패하면 |
|---|---|---|
| G0 Specification | 팀 API contract 문서 합의 | 코드 시작 금지 |
| G1 Korean Core | unit test 100% pass | LLM 연결 미룸 |
| G2 Mock API | `/predict`가 mock으로 안정 동작 | UI/LLM 병렬개발 중지 후 수정 |
| G3 Live LLM | 50개 sanity set에서 schema failure 거의 없음 | prompt/schema 수정 |
| G4 Offline Eval | held-out test 성능 표 생성 가능 | EEG 연결 전에 language pipeline 개선 |
| G5 EEG Contract | 실제 decoder sample JSON 수신 | fusion 구현 금지 |
| G6 Integration | P300→backend→UI round trip 동작 | 사용자 pilot 금지 |
| G7 Pilot | 오류 복구/로그/latency 측정 가능 | 본 실험 금지 |
| G8 Research Run | 조건 A/B/C/D 비교 데이터 확보 | hybrid 최종 주장 금지 |
| G9 Reproducibility | clean machine에서 README만 보고 재현 | 최종 제출 전 수정 |

가장 중요한 규칙:

```text
앞 단계가 실패했는데 다음 단계 기능을 추가해서 가리는 행동을 하지 않는다.
```

---

# 56. 연구 진행 순서

## Phase 0 — Specification

완료 기준:

```text
API contract 문서화
InputMode 확정
Context schema 확정
Top-K 확정
```

## Phase 1 — Deterministic Korean Core

```text
initial extraction
validation
Auto Toggle
filter
unit tests
```

## Phase 2 — LLM MVP

```text
OpenAI
Structured Outputs
12 candidates
Top-3
```

## Phase 3 — Context

```text
partner
situation
current_sentence
recent_context
```

## Phase 4 — Offline Eval

```text
dataset
Acc@1
Acc@3
MRR
latency
```

## Phase 5 — EEG Fusion

```text
top-k EEG
joint ranking
```

## Phase 6 — Frontend Integration

```text
P300 UI
candidate SSVEP UI
sentence buffer
```

## Phase 7 — Pilot

```text
healthy participants / internal pilot
error taxonomy
latency
```

## Phase 8 — Hybrid Strategy

```text
initials ↔ Auto Toggle automatic switch
```

## Phase 9 — End-to-End

```text
EEG → P300 → LLM → SSVEP → sentence → speech
```

---

# 57. 이번 주 바로 할 일

다음 순서로 하면 된다.

## Task 1

GitHub private repository 생성.

## Task 2

`backend/`, `frontend/`, `docs/`, `research/` 구조 생성.

## Task 3

`shared/api_contract.md` 작성.

## Task 4

`schemas.py` 작성.

## Task 5

`korean/initials.py`와 unit test.

## Task 6

`korean/composer.py`와 Auto Toggle unit test.

## Task 7

Mock `/predict` API.

## Task 8

가빈 UI가 Mock `/predict`를 호출하게 함.

## Task 9

실제 OpenAI CandidateGenerator 추가.

## Task 10

10~20개 생성 → hard filter → Top-3.

## Task 11

`eval/dev_v1.jsonl` 50개부터 작성.

## Task 12

Acc@1/3 evaluator 작성.

---

# 58. 9월 목표

```text
[ ] Backend 독립 실행
[ ] Initials mode
[ ] Auto Toggle mode
[ ] OpenAI 호출
[ ] Mock mode
[ ] Context
[ ] Top-K
[ ] API contract
[ ] UI mock integration
[ ] EEG input schema 준비
[ ] 기본 평가 dataset
```

완료되면 “장비가 없어도 language system은 연구 가능한 상태”다.

---

# 59. 10월 목표

```text
[ ] 200~300개 dataset
[ ] dev/test split
[ ] prompt comparison
[ ] context ablation
[ ] model benchmark
[ ] Acc@1/3/MRR
[ ] latency
[ ] Auto Toggle vs Initials offline simulation
```

---

# 60. 11월 목표

```text
[ ] 실제 EEG top-k integration
[ ] EEG-language fusion
[ ] error reranking
[ ] A/B/C/D conditions
[ ] KSR
[ ] completion time
[ ] correction count
```

---

# 61. 12월~1월 목표

```text
[ ] adaptive hybrid
[ ] End-to-End prototype
[ ] speech output
[ ] final participant evaluation
[ ] analysis plots
[ ] technical report
[ ] final demo
```

---

# 62. 최종 연구 결과표 템플릿

## 입력 전략 비교

| Mode | Acc@3 | selections | completion time | correction | success |
|---|---:|---:|---:|---:|---:|
| Auto Toggle | | | | | |
| Auto Toggle + LLM | | | | | |
| Initials + LLM | | | | | |
| Hybrid | | | | | |

## Context ablation

| Context | Acc@1 | Acc@3 | MRR |
|---|---:|---:|---:|
| none | | | |
| partner | | | |
| partner+situation | | | |
| full context | | | |

## Model

| Model | Acc@3 | latency | cost |
|---|---:|---:|---:|
| Luna | | | |
| Terra | | | |
| Sol | | | |

---

# 63. 최종 보고서에서 준서가 작성할 Section

```text
1. Korean Language Prediction Architecture
2. Korean Input Representation
3. Initials Mode
4. Auto Toggle State Machine
5. Context Representation
6. LLM Candidate Generation
7. Deterministic Candidate Validation
8. Candidate Ranking
9. EEG-Language Fusion
10. Error Reranking
11. API Architecture
12. Evaluation Dataset
13. Metrics
14. Context Ablation
15. Input-mode Comparison
16. Latency Analysis
17. Failure Analysis
18. Limitations
19. Future Work
```

---

# 64. 가장 중요한 연구 질문 4개

## RQ1

초성열 기반 LLM prediction이 Auto Toggle 직접 입력보다 EEG 선택 수를 줄이는가?

## RQ2

대화 상대·상황·최근 대화를 제공하면 추천 정확도가 증가하는가?

## RQ3

EEG top-k uncertainty와 language prior를 결합하면 EEG argmax만 사용하는 방식보다 최종 의도 복원률이 높아지는가?

## RQ4

초성열과 Auto Toggle을 상황에 따라 전환하는 Hybrid 방식이 각 단독 방식보다 communication efficiency가 좋은가?

---

# 65. 지금 절대 하지 않아도 되는 것

초기 버전에서 다음은 과하다.

```text
LLM 직접 학습
Fine-tuning
RAG
Vector DB
Multi-agent
Kubernetes
복잡한 microservice
큰 SQL database
```

먼저 **작동하고 측정 가능한 단일 backend**를 완성한다.

---

# 66. 향후 고도화 아이디어

v2 이후:

- 개인별 자주 쓰는 표현 ranking
- candidate embedding diversity
- calibrated uncertainty
- local Korean language model fallback
- user adaptive vocabulary
- online learning without raw private text
- sentence-level prediction
- emergency phrase layer
- gaze AAC input support
- switch input support

---

# 67. Emergency Communication

호흡 곤란 등 긴급 의사표현은 LLM 추천 성공에만 의존하지 않는 것이 좋다.

별도 quick-access phrase bank를 연구/UX 관점에서 검토한다.

예:

```text
도와주세요
숨쉬기 힘들어요
통증이 있어요
자세를 바꿔주세요
```

이는 LLM이 생성하는 medical advice가 아니라 **사용자 발화 선택지**다.

---

# 68. Production 전 보안 Checklist

```text
[ ] .env GitHub에 없음
[ ] API Key frontend bundle에 없음
[ ] CORS actual domain만 허용
[ ] debug response off
[ ] raw sensitive context logging off
[ ] HTTPS
[ ] request size limit
[ ] timeout
[ ] rate limit 고려
[ ] API cost alert
[ ] test participant ID pseudonymized
```

---

# 69. Pilot 전 Checklist

```text
[ ] 모든 unit test pass
[ ] mock integration pass
[ ] live OpenAI integration pass
[ ] staging UI 정상
[ ] EEG decoder contract 정상
[ ] SSVEP candidate_id mapping 정상
[ ] logging 정상
[ ] undo 정상
[ ] LLM timeout fallback 정상
[ ] internet 끊김 fallback 확인
[ ] experiment mode가 로그에 저장됨
[ ] test prompt/model version 고정
```

---



# 69.5. 최종 제출 폴더에 반드시 존재해야 하는 파일

```text
README.md                  # 다른 사람이 실행하는 문서
INTERFACES.md              # 팀 API 계약
RESEARCH_PROTOCOL.md       # 조건/순서/평가 지표
PROMPT_CHANGELOG.md        # prompt 변경 이력
MODEL_BENCHMARK.md         # Luna/Terra/Sol 비교
FAILURE_ANALYSIS.md        # 실패 유형/예시/개선
SECURITY.md                # secret/로그/배포 규칙
CHANGELOG.md               # pipeline version 변경
requirements.txt 또는 pyproject.toml
.env.example
Dockerfile
app/
tests/
eval/
data/templates/            # 개인정보 없는 schema/template만
results/summary/           # aggregate 결과만
```

원자료(raw participant data)는 공개 Git repository에 넣지 않는다.

---

# 70. Definition of Done — 준서 파트 최종 완료 기준

다음이 전부 체크되면 준서 파트는 완료라고 볼 수 있다.

## Language Core

- [ ] 초성 추출
- [ ] 초성 validation
- [ ] Auto Toggle 조합
- [ ] normalize

## LLM

- [ ] OpenAI API 연결
- [ ] Structured Outputs
- [ ] generation prompt
- [ ] context support
- [ ] 10~20 후보 내부 생성

## Postprocessing

- [ ] hard filter
- [ ] canonical duplicate
- [ ] ranking
- [ ] Top-K
- [ ] fallback

## EEG

- [ ] top-k hypothesis schema
- [ ] fusion
- [ ] uncertain reranking

## API

- [ ] `/health`
- [ ] `/predict`
- [ ] `/autotoggle/step`
- [ ] session reset/undo

## Research

- [ ] dataset
- [ ] dev/test split
- [ ] Acc@1
- [ ] Acc@3
- [ ] MRR
- [ ] KSR
- [ ] latency
- [ ] four-condition comparison
- [ ] context ablation
- [ ] failure taxonomy

## Integration

- [ ] React UI connection
- [ ] P300 decoder connection
- [ ] SSVEP result connection
- [ ] sentence buffer
- [ ] End-to-End demo

## Engineering

- [ ] private GitHub
- [ ] branch workflow
- [ ] tests
- [ ] staging deployment
- [ ] production deployment
- [ ] security checklist
- [ ] README/current docs

---

# 71. 이 프로젝트를 설계할 때 계속 기억할 문장

```text
LLM은 사용자 대신 말하는 존재가 아니다.
LLM은 사용자의 불완전하고 불확실한 BCI 입력을 언어 문맥으로 보조하여
더 적은 EEG 선택으로 사용자의 실제 의도에 도달하도록 돕는 language prior이다.
```

그리고 연구의 최종 질문은:

```text
“우리 LLM이 얼마나 똑똑한가?”
```

가 아니라:

```text
“이 시스템을 사용했을 때 사람이 원하는 말을 더 적은 선택과 더 짧은 시간으로 전달할 수 있는가?”
```

이다.

---

# 72. 공식 문서 / 참고 링크

## OpenAI

- Model guide: https://developers.openai.com/api/docs/guides/latest-model
- Models: https://developers.openai.com/api/docs/models
- GPT-5.6 Luna: https://developers.openai.com/api/docs/models/gpt-5.6-luna
- GPT-5.6 Terra: https://developers.openai.com/api/docs/models/gpt-5.6-terra
- GPT-5.6 Sol: https://developers.openai.com/api/docs/models/gpt-5.6-sol

## FastAPI

- https://fastapi.tiangolo.com/

## Pydantic

- https://docs.pydantic.dev/

## React

- https://react.dev/

---



# 72.5. 지금부터 72시간 실제 작업 계획

## 오늘 밤 — “코드보다 계약”을 끝낸다

### 1. GitHub repository 준비

```text
bci-korean-speller/
```

private repository로 시작한다.

### 2. Issues 10개를 만든다

```text
#1 API contract
#2 Korean initials core
#3 Auto Toggle spec
#4 Mock /predict
#5 OpenAI candidate generator
#6 Offline eval dataset
#7 Context ablation
#8 EEG decoder contract
#9 React integration
#10 Deployment/staging
```

### 3. 팀에 `INTERFACES.md` 공유

아직 코드보다 이 파일이 중요하다.

박필과 합의할 최소 필드:

```json
{
  "trial_id": "T001",
  "timestamp_ms": 0,
  "decoder": "p300-v1",
  "hypotheses": [
    {"input": "ㄷ", "decoder_score": 0.73},
    {"input": "ㅌ", "decoder_score": 0.16}
  ],
  "score_type": "probability",
  "decoder_latency_ms": 820
}
```

가빈에게 줄 최소 response:

```json
{
  "trial_id": "T001",
  "candidates": [
    {"id": "c1", "text": "도와줘", "rank": 1},
    {"id": "c2", "text": "들어줘", "rank": 2},
    {"id": "c3", "text": "다음 주", "rank": 3}
  ],
  "fallback_actions": ["more", "reinput"],
  "latency_ms": 420
}
```

### 4. 연구 mode 이름 확정

```text
A_baseline_autotoggle
B_autotoggle_llm
C_initials_llm
D_hybrid
```

로그, 그래프, 보고서에서 이름을 바꾸지 않는다.

## 내일 — deterministic core + mock

완료해야 할 것:

- `extract_initials`
- `normalize_initials`
- `exact_initial_match`
- Auto Toggle 기본 state
- Pydantic schema
- mock generator
- `/predict`
- `/health`
- `pytest`

이날은 API credit을 거의 쓰지 않아도 된다.

## 모레 — live LLM + eval harness

완료해야 할 것:

- `.env` secret
- OpenAI Responses API
- Structured Outputs
- 최소 50개 sanity dataset
- `Acc@1/3`, MRR, latency
- failure case CSV/JSONL

이 시점에 처음으로 prompt를 본격적으로 고친다.

---

# 73. 마지막 — 오늘부터 그대로 따라 할 순서

이 부분만 출력해서 책상 옆에 붙여도 된다.

```text
DAY 1
□ Private GitHub repo
□ backend/frontend/docs/research 폴더
□ API contract
□ Pydantic schema

DAY 2
□ Korean initials.py
□ exact match
□ tests
□ Auto Toggle composer

DAY 3
□ Mock candidate generator
□ FastAPI /predict
□ Swagger test

DAY 4
□ OpenAI API
□ Structured Outputs
□ 12 candidates
□ hard filter

DAY 5
□ context manager
□ ranking
□ Top-3
□ fallback

DAY 6
□ React mock integration
□ loading/error/reinput
□ sentence buffer

DAY 7
□ evaluation dataset 50개
□ Acc@1/3/MRR
□ latency log

NEXT
□ dataset 200~300개
□ EEG top-k connection
□ EEG-language fusion
□ Auto Toggle vs Initials
□ Hybrid
□ End-to-End
```

---

## 문서 버전

```text
README version: final-ko-v2.0-audited
작성 기준일: 2026-08-30
```

이 README를 코드와 함께 계속 업데이트한다.



---

# 부록 A. 최종 권장 의사결정 표

| 결정 | 지금 기본값 | 언제 바꿀까 |
|---|---|---|
| 내부 후보 수 | 12 | valid 후보 부족/latency 분석 후 |
| UI 후보 수 | 3 | SSVEP protocol과 사용자 pilot 결과 후 |
| 모델 | Luna부터 benchmark | held-out accuracy/latency/cost 결과 후 |
| reasoning effort | low/none 후보 비교 | 품질 이득이 latency를 정당화할 때 |
| EEG hypothesis top-k | 3~5 | decoder confusion 분석 후 |
| context history | 최근 3~5 turn | ablation 후 |
| retry | 1회 | failure rate/latency 분석 후 |
| fallback | reinput + more | UI pilot 후 |
| CORS | localhost만(dev) | staging/production 실제 domain으로 |
| 로그 원문 | 최소화 | 연구윤리/분석계획에 따라 |

# 부록 B. 매 회의 때 준서가 보고할 8개 숫자

```text
1. offline Acc@1
2. offline Acc@3
3. MRR
4. valid-candidate rate
5. schema/API failure rate
6. p50 latency
7. p95 latency
8. 평균 API cost/request
```

EEG 통합 뒤에는 추가:

```text
9. selection count
10. completion time
11. correction count
12. final success rate
```

# 부록 C. 연구 발표에서 피해야 할 과장 표현

피한다:

```text
LLM이 환자의 생각을 읽는다.
EEG와 LLM으로 의도를 정확히 복원한다.
0.9 score이므로 90% 확률이다.
Bayesian posterior를 계산했다.  # calibration이 없으면
ALS 환자에게 효과가 입증됐다.   # ALS 대상 실증 전이면
```

권장:

```text
부분 EEG 기반 입력과 대화 문맥을 이용해 후보를 재순위화한다.
한국어 초성/자모 입력의 선택 효율을 비교한다.
held-out dataset에서 Top-3 적중률을 평가한다.
파일럿 참가자에서 선택 횟수와 문장 완성 시간을 비교한다.
```

# 부록 D. 매일 끝나기 전 10분 체크

```text
[ ] 오늘 변경한 코드가 issue와 연결되어 있는가
[ ] unit test가 통과하는가
[ ] API key가 git에 들어가지 않았는가
[ ] prompt/model/pipeline version을 기록했는가
[ ] 실제 participant 정보가 test fixture에 들어가지 않았는가
[ ] 변경 전후 metric을 하나라도 비교했는가
[ ] 실패 사례를 지우지 않고 기록했는가
[ ] README 실행 명령이 여전히 맞는가
[ ] 다른 팀원이 interface 변경을 알고 있는가
[ ] main에 merge할 준비가 되었는가
```

**최종 원칙:** 기능을 많이 넣는 것보다, `입력 → 후보 → 선택 → 문장`의 한 cycle을 빠르고 측정 가능하고 재현 가능하게 만드는 것이 우선이다.
