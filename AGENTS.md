# 이심전심 BCI Speller — 에이전트 규칙 (Claude·Codex 공통, 모든 작업에 먼저 적용)

## A. 토큰 최소화
- 통째로 읽지 않는다: `app/static/bci_speller.html`(670KB), `app/static/dict.txt`(12MB, 열지 않음), `app/pipeline/service.py`(1,100줄). `grep -n` → ±40줄만 Read → Edit, 재독 금지.
- 핵심 위치: `const SCORE=` · `localWords/sentenceSlots/decodeSentences` · `handleKey/pressSpace/pressCommitKey` · 서버 `app/llm/prompts.py`, `openai_client.py`, `app/pipeline/filter.py`. 프로젝트 문서는 최신 1개만.
- 최소 변경: 기존 함수·CSS 변수 재사용, 새 파일·의존성·리팩터링은 요청 시만. 여러 곳은 Python 한 번(`assert s.count(a)==1` 후 replace).
- 검증은 관련 테스트 먼저(`pytest -q tests/<관련>.py`, `node --test --test-name-pattern=…`), 커밋 전 전체 1회. 스크린샷은 화면 변경 시만 2장(데스크톱·모바일).
- 질문은 막혔을 때만 1회. 서브에이전트·워크플로 금지. 보고는 변경 사항 / 검증 결과 / 남은 문제 3묶음.
- **이 파일은 살아 있는 문서다**: 작업을 끝낼 때마다 새로 확정된 원칙·함정·실패한 시도는 B에 추가하고, 끝난 "다음 할 일"·낡은 수치·더는 안 쓰는 규칙은 지운다. 30줄 안팎을 유지하고 같은 커밋에 넣는다.

## B. 결과물 목표 — 이때까지의 개발에서 확정된 원칙 (어기지 말 것)
1. **목표**: 발화·운동 제한 사용자가 최소 응시 선택으로 말한다. 모든 변경은 "선택 횟수·루프 시간이 줄어드는가"로 판단한다.
2. **로컬이 먼저, LLM은 보조**: 키마다 브라우저 로컬 후보가 ~1ms에 7칸을 채운다(내 기록 → 검수 AAC 281 → 환자 4,052 → 말뭉치 → 사전 45.9만+n-gram). LLM은 못 채운 문장 칸만, 늦게 와도 **이미 보이는 후보 번호는 절대 바꾸지 않는다**. 서버가 죽어도 입력은 계속된다.
3. **입력 구조**: 기본은 환자 실험용 자판(피그마 88:948 자음판 29키 = 후보 1~5·자음·자모변환·된소리 + 문장 말하기·띄어쓰기·?·없음·확정, 88:757 모음판 25키), `kbLayout` fig. 40키 두벌식(4×10, ChatBCI·MindChat 비교용)은 설정 '자판'에서 고르고 벤치·기존 테스트의 기준(`KB=k40`, `HTML('k40')`). 받침은 후보가 채운다. 띄기 = 어절 경계, 초성 최대 40. 후보 5칸은 사용자 디자인 결정 — 7칸 대비 일상 실효 32.4→29.3, AAC 52.5→51.0(더 큰 키·적은 자극 수와 맞바꿈).
4. **시선 열**: 내가 할 말 → 후보 → 자판을 한 열에. SSVEP 자극 중 나머지는 어둡게, 자판 카드는 불투명·진입 애니메이션 금지.
5. **LLM 연동**: Responses API 구조화 JSON, 모든 후보는 Python이 초성 정확 일치·고정 글자를 재검증. 문맥은 "데이터이지 명령이 아님". reasoning none(지원 안 되면 minimal→low), retryable 오류만 2회 재시도. 띄어 친 경계를 문맥으로 준다(0개 응답 60→32.5%).
6. **측정으로 결정**: 후보 품질 변경은 4세트(검수 AAC · 일상 보류 · 사전 용례 · 환자 보류)의 **실효 절감**으로 비교(`tools/bench_general.cjs`, `bench_decode.cjs`, 대화 문맥은 `bench_dialog.cjs`; 일상 보류 파일은 `CHAT_TEST=/home/claude/data/chat_test.txt`), 한 세트라도 크게 나빠지면 기각. 외운 표현 수치(93.6%)로 자랑하지 않는다.
7. **알려진 함정**: 서버 import는 `requirements.deploy.txt`에 있는 것만(requests 넣었다가 Render가 v3.0에 멈춤 — CI가 이제 막음) · 초성 0개 구간은 n-gram 전용(주제·에코를 넣으면 손해) · backoff는 점수 섞기가 아니라 순서 · 에코 조각은 끝 글자가 조사일 때만 뗀다(허리→허 같은 조각이 1번 칸 차지) · `""`(내 차례 첫 단어)도 문맥 · 넓은 층은 늘 좁은 층보다 낮은 점수 · 벤치 하나만 보고 층을 지우지 않는다 · SSVEP 점멸은 "동작 줄이기"(Windows 애니메이션 끔)에서도 켜 둔다 — 전역 animation:none이 실험 자극까지 꺼서 "깜빡임이 사라졌다"는 신고(v3.5.2) · 고정 글자 비교는 띄어쓰기를 뺀 글자 순서로(`pinnedOk`) — 원문 위치로 비교해 "물 좀 주세요"가 {2:'주'}에서 빠졌었다 · 없음으로 글자 채우는 중(`jamoTarget`)에 지우기·초기화·후보 선택이 오면 `clearRecoveryState`가 모음판·안내를 함께 끝낸다(안 그러면 다음 자음이 받침으로 들어감) · STEM_END에 `까|래` 한 글자 어미를 넣으면 dialog·ctxall 둘 다 하락(실패).
8. **다시 시도하지 말 것(측정상 실패)**: 후보 5개 축소, 조사 합성 층, 문장 복원 단어 가산점·빔 16, 0초성 상황어 주입, NSMC 말뭉치, LLM 재시도·음절칸 프롬프트, reasoning low(15초).
9. **디자인**: 장식(유리·빛줄기·파형·네온·무지개) 금지 — 사용자가 "로봇 같다·촌스럽다"고 거절함. 내용·글자·여백으로 위계, 색 토큰 3~4개, 대비 AA, clamp() 유동 크기, 누를 자리 48px 이상(작은 버튼은 오선택 원인).
   디자인 원본은 피그마(파일 ZGUwwyRYckZHF1wFsdinUP, Main 88:948·모음 88:757·40키 26:17·loading 4:11): 연초록 그라데이션 #B1DCB0→#DDE0C6 · 흰 카드(테두리 #D9DEDB, 둥글기 26) · 초록 #3C7D5E/#3D6B50 · 명조(Noto Serif KR) · 以心傳心 로고. 값은 맨 끝 "Figma 디자인" CSS 블록 하나에만. 피그마 MCP는 월 20회 — metadata/스크린샷으로 먼저 보고 필요한 프레임만 읽는다. 어두운 화면(다크모드)은 없앰 — 늘 밝은 화면(`data-theme="light"` 고정, 남은 `html:not([data-theme="dark"])` 접두는 무해). SSVEP 자극은 Cao et al.(EMBC)대로 배경 #202020, 밝은 상태 #FFFFFF, 어두운 상태 #404040, 안내 글씨 #DDDDDD.
10. **v3.4 반영됨**: 에코 = 상대 3마디 + 내가 끝낸 2마디(×`echoMine`)·반복어 +`echoRepeat`·`echo` 900, 어간(목욕할까요→목욕, 영희네→영희)과 그 어간으로 시작하는 말 ×`echoStem`, 묻는 꼴(할까요·갈래)은 통째 ×.4, 대화 단어는 접두만 맞아도 `prefix` 점수 · 답장 단어 `/reply-words` · 뉴스 화제어는 동점 깨기(`trend` 8)만 · Enter=문장 완료, 끝낸 문장은 '내가 할 말' 윗줄(`#prevLines`), 확정 키가 ↵ 엔터로 바뀜 · `keepalive.yml` 10분 핑(Render 잠 방지). **v3.9**: "없음"(0) → `bestSpellTarget("staged")`가 후보를 가장 가르는 질문 하나(빈 자리의 모음, 또는 모음만 고른 자리의 받침)를 고름 → 빨간 글자 · 모음판 → 모음 하나로 바로 재검색(`vowelOnly`, 받침 자유) / 받침 질문이면 자음판에서 받침(✓=없음), ⌫=취소. `bench_none.cjs` 선택 수 14.03(모음+받침 한 번에)→12.69. 손으로 친 모음도 `vowelOnly`(무→물·문). 서버엔 다 고른 글자만(`fullSpelled`). 뉴스: 서버 `analyze`가 7개 분야 제목을 이슈로 묶고 화제어 점수(이틀 반감) → '요즘 이야깃거리' 선택, 상대가 "요즘 야구 봤어?"처럼 물을 때만(`NEWS_CUE`) 분야 1위 이슈를 문맥·답장 단어에. **다음 할 일**: 실제 대화 기록으로 dialog 세트 늘리기(32대화는 손으로 씀) · 오선택 기록으로 키 크기 조정.
11. **정직·안전**: 실제 EEG 미연결을 화면·문서에 명시, 수치는 보류 세트 기준으로만. 데이터는 라이선스 확인(전공서·원문 재배포 금지), 개인 학습은 기기에만, `.env`의 API 키는 읽지도 출력하지도 않는다.
12. **완료 기준**: 테스트 전부 통과 → 버전 문자열(푸터·eyebrow·metrics) 올림 (origin/main 값 기준 — WIP·이전 배포가 이미 올렸을 수 있다) → 배포 후 `curl …/speller | grep -o "· v[0-9.]*<"`로 라이브 확인 → 프로젝트 문서 1개(변경·측정·한계).

## C. 배포
- PC에서는 바로 push. 클라우드 컨테이너는 bundle → PC 임시 worktree에서 커밋·push. 사용자 작업 트리와 커밋 안 된 변경은 절대 건드리지 않는다(시작 전 `git status -sb`). CI 10~18분 뒤 자동 배포. 라이브가 안 바뀌면 `/health`의 release와 라이브 HTML이 어느 커밋과 같은지부터 본다(배포 실패면 이전 버전이 계속 뜬다). 라이브가 응답 없이 멈추면(코드는 로컬 정상) 커밋 push로 새 배포를 띄운다. CI 실패는 단계부터 본다(`/actions/runs/{id}/jobs`) — playwright 설치 실패는 인프라라 재시도로 넘긴다. keepalive 예약은 GitHub가 실제로 3~4시간 간격으로만 돌린다 — 그래서 `sw.js`가 두 번째 방문부터 1.5초 안에 저장본을 연다(Render 로딩 화면은 `id="keyboard"` 검사로 저장 안 함). 첫 방문까지 없애려면 외부 5분 핑(UptimeRobot) 또는 유료 플랜.

## D. 피그마 반영 ("피그마 바꿨어"라고 하면)
- 순서: `get_metadata 0:1`로 바뀐 프레임 찾기 → 그 프레임만 `get_design_context`(스크린샷 포함) → 값은 "Figma 디자인" CSS 블록, 배치·기능 변화는 해당 DOM/JS 최소 수정 → 데스크톱·모바일 스크린샷 비교 → 배포. 40키·48px·SSVEP 원칙과 부딪히면 먼저 묻는다.
- 기준 화면은 TV 1920×1044(피그마 Main 크기): 스크롤 없이 연구용 안내 푸터까지 한 화면(`@media(min-width:1800px) and (min-height:1000px)` 블록). 바꾼 뒤 `scrollHeight==1044` 확인.
- 레이어 이름 → 코드: Conversation toolbar=`.topline` · Conversation=`.card.chat`(My/Partner bubble=`.chat-turn.me/.partner .tx`) · Sentence composer=`.card.mine`·`.buffer` · Word candidates=`#candWords`(Candidate=`.cand.word`) · Korean input keyboard=`#keyboard`(줄=`.kb-row`, Keyboard key=`.kb .key.cho/.jung/.fn/.cand`, 아래 줄 Action=`.key.pill`, Korean vowel input keyboard=`.kb.vowel`) · loadin screen=`#splash`(1.1초 뒤 로고가 `.brand-logo` 자리로 날아감, Web Animations라 동작 줄이기에서도 보임, 탭당 1회).
