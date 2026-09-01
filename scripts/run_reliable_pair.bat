@echo off
setlocal

echo ============================================================
echo  BCI reliable 150-case evaluation with retry + resume
echo ============================================================
echo.

set MOCK_MODE=false
set DATASET=eval\datasets\test_v1_150.jsonl

echo [1/2] Baseline v2 reliable run
set ENSEMBLE_MODE=off
python -m eval.run_test_resume --dataset "%DATASET%" --label baseline_v2_reliable --max-retries 3 --between-cases 1.0
if errorlevel 2 (
  echo.
  echo Baseline still has service errors.
  echo Run this BAT again later. Successful cases will be skipped automatically.
  exit /b 2
)

echo.
echo [2/2] v6.3 context-quality reliable run
set ENSEMBLE_MODE=context_quality
set ENSEMBLE_MIN_VALID=6
set ENSEMBLE_MAX_FIRST_TOKEN_RATIO=0.50
set ENSEMBLE_CONTEXT_THRESHOLD=0.72
set ENSEMBLE_INTENT_THRESHOLD=0.72
set DIVERSITY_GENERATION_COUNT=8

python -m eval.run_test_resume --dataset "%DATASET%" --label v6_3_context_quality_reliable --max-retries 3 --between-cases 1.0
if errorlevel 2 (
  echo.
  echo v6.3 still has service errors.
  echo Run this BAT again later. Successful cases will be skipped automatically.
  exit /b 2
)

echo.
echo [COMPARE]
python -m eval.compare_reliable_runs

endlocal
