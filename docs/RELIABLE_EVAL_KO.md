# BCI Reliable Eval Patch V1

현재 150-case 평가에서 baseline과 v6.3 모두 connection_error가 대량 발생한 경우를 위한 패치입니다.

핵심:
- case 성공 즉시 checkpoint 저장
- 성공한 case는 재실행 시 skip
- connection/timeout/rate-limit 계열 오류는 exponential backoff로 최대 3회 재시도
- 파이프라인이 fallback으로 숨긴 transient warning도 service error로 판정해 재시도
- 최종 service_error_count가 0이 아니면 valid_for_reporting=false
- baseline과 v6.3 모두 service_error_count=0일 때만 비교

사용:
1. ZIP 내용을 프로젝트 루트에 병합
2. `python -m py_compile eval\run_test_resume.py eval\compare_reliable_runs.py`
3. `python -m pytest -q`
4. `scripts\run_reliable_pair.bat`

중간에 네트워크가 끊겨도 같은 BAT를 다시 실행하면 성공 케이스는 건너뛰고 실패 케이스만 다시 수행합니다.
