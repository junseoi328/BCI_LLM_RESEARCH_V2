@echo off
setlocal
echo FINAL locked 150-case evaluation.
echo Run this only after the v7 configuration is frozen.
pause
python -m eval.benchmark_v7_pipeline --dataset eval\datasets\test_v1_150.jsonl --final-test
endlocal
