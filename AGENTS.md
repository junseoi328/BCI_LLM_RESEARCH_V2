# 이심전심 BCI Speller — 토큰 최소 개발 규칙 (Claude·Codex 공통, 모든 작업에 먼저 적용)

## 읽기
- 큰 파일은 통째로 읽지 않는다: `app/static/bci_speller.html`(약 670KB, 화면+엔진 전부), `app/static/dict.txt`(12MB, 절대 열지 않음), `app/pipeline/service.py`(1,100줄).
- 순서: `grep -n "함수명|id"` → 해당 줄 ±40줄만 Read → Edit. 같은 곳을 두 번 읽지 않는다.
- 프로젝트 문서는 최신 1개(`claude/` 맨 위)만 읽고, 과거 이력은 질문받을 때만 `project_search`.
- 핵심 위치: 점수 상수 `const SCORE=` · 후보 `localWords/sentenceSlots/decodeSentences` · 입력 `handleKey/pressSpace` · 서버 `app/llm/prompts.py`, `openai_client.py`, `app/pipeline/filter.py`.

## 고치기
- 최소 변경: 기존 함수·토큰(CSS 변수) 재사용, 새 파일·의존성·리팩터링 금지(요청 시만).
- 여러 군데 수정은 Python 한 번(`assert s.count(a)==1` 후 replace)으로 묶는다.
- 주석은 "왜"만 한 줄. 측정값이 있으면 숫자로.

## 검증 (필요한 것만, 한 번씩)
- 서버: `python3 -m pytest -q tests/<관련파일>.py` → 커밋 전 `python3 -m pytest -q` 1회.
- 화면: `node --test --test-name-pattern="<관련>" tests/speller_ui.test.cjs` → 커밋 전 전체 1회.
- 후보 품질을 건드렸을 때만: `node tools/bench_general.cjs app/static/bci_speller.html x`(파라미터 탐색은 `SCORE_JSON='{...}'`), 문장 복원은 `tools/bench_decode.cjs`(`SPACED=1`).
- 스크린샷은 화면을 바꿨을 때만, 최대 2장(데스크톱·모바일), 낮은 해상도.
- 실제 LLM 호출 평가(`tools/eval_generator.py`)는 비용이 드니 요청받았을 때만.

## 배포
- PC에서는 바로 push. 클라우드 컨테이너는 push 불가 → bundle을 PC로 보내 Windows git으로 push(사용자 작업 트리는 건드리지 말고 임시 worktree 사용).
- 커밋 안 된 사용자 변경은 절대 덮어쓰지 않는다. 시작 전 `git status -sb` 한 번.
- 확인은 폴링 한 번: `curl -s …/speller | grep -o "· v[0-9.]*<"`(CI 10~18분). 버전 문자열(푸터·eyebrow·metrics)만 올린다.

## 대화
- 막혔을 때만 질문 1회. 서브에이전트·워크플로·긴 계획서 금지.
- 최종 보고는 3줄 묶음: 변경 사항 / 검증 결과 / 남은 문제. 코드·로그를 채팅에 붙이지 않는다.
- 비밀값(.env의 OPENAI_API_KEY)은 읽지도 출력하지도 않는다.
