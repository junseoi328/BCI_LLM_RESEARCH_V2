# 이심전심 BCI Speller — 토큰 최소 개발 규칙 (Claude·Codex 공통, 모든 작업에 먼저 적용)
## 읽기
- 통째로 읽지 않는다: `app/static/bci_speller.html`(670KB), `app/static/dict.txt`(12MB, 열지 않음), `app/pipeline/service.py`(1,100줄). `grep -n` → 해당 줄 ±40줄만 Read → Edit, 같은 곳 재독 금지.
- 핵심 위치: `const SCORE=` · `localWords/sentenceSlots/decodeSentences` · `handleKey/pressSpace` · 서버 `app/llm/prompts.py`, `openai_client.py`, `app/pipeline/filter.py`. 프로젝트 문서는 최신 1개만.
## 고치기
- 최소 변경: 기존 함수·CSS 변수 재사용, 새 파일·의존성·리팩터링 금지(요청 시만). 여러 곳은 Python 한 번(`assert s.count(a)==1` 후 replace). 주석은 "왜"만 한 줄.
## 갤럭시(안드로이드 크롬·삼성 인터넷) 오류 방지 — 화면을 고칠 때마다 지킨다
- 고정 하단바·상단바·자판에 `backdrop-filter` 금지(줄무늬·깜빡임). 불투명 배경을 먼저 쓰고, 흐림은 `@supports`로만 덧붙인다.
- 높이는 `100vh` 대신 `min-height:100dvh`(앞줄에 `100vh` 대체값). 하단 고정 요소는 `bottom:calc(Npx + env(safe-area-inset-bottom))`, viewport 메타 `viewport-fit=cover, interactive-widget=resizes-content`.
- 시스템 글꼴 크기 130%에서도 안 깨지게: 고정 `height` 대신 `min-height`, 탭·버튼 글자는 `white-space:nowrap; min-width:0; overflow:hidden; text-overflow:ellipsis`, `text-size-adjust:100%`.
- 삼성 인터넷 강제 다크 방지: `<meta name="color-scheme" content="light dark">` + 다크 토큰을 직접 정의. 글자·배경 대비 AA 유지.
- 핵심 동작을 `:has()`·`color-mix()`에만 맡기지 않는다: JS로 클래스 토글하고, `color-mix` 앞줄에 일반 색 대체값을 둔다.
- 터치: 누를 자리 48px 이상, `touch-action:manipulation`, `-webkit-tap-highlight-color:transparent`. hover 효과는 `@media(hover:hover)` 안에만.
- 확인: Playwright 360×740·412×915(DPR 3, `isMobile:true, hasTouch:true`)에서 가로 넘침 0·하단바가 내용 가리지 않음·글꼴 130%(`html{font-size:130%}`) 3가지만 검사.
## 검증 (필요한 것만, 한 번씩)
- 서버 `python3 -m pytest -q tests/<관련>.py`, 화면 `node --test --test-name-pattern="<관련>" tests/speller_ui.test.cjs` → 커밋 전 전체 1회.
- 후보 품질을 건드렸을 때만 `tools/bench_general.cjs`(`SCORE_JSON`)·`tools/bench_decode.cjs`(`SPACED=1`). 실제 LLM 평가(`tools/eval_generator.py`)는 요청 시만.
- 스크린샷은 화면 변경 시만, 최대 2장(데스크톱·갤럭시 폭 360), 낮은 해상도.
## 배포
- PC는 바로 push. 클라우드 컨테이너는 bundle → PC 임시 worktree에서 커밋·push(사용자 작업 트리·커밋 안 된 변경은 절대 건드리지 않음, 시작 전 `git status -sb`).
- 확인은 폴링 한 번: `curl -s …/speller | grep -o "· v[0-9.]*<"`(CI 10~18분). 버전 문자열(푸터·eyebrow·metrics)만 올린다.
## 대화
- 막혔을 때만 질문 1회. 서브에이전트·워크플로·긴 계획서 금지. 보고는 변경 사항 / 검증 결과 / 남은 문제 3묶음, 코드·로그는 붙이지 않는다.
- 비밀값(.env의 OPENAI_API_KEY)은 읽지도 출력하지도 않는다.
