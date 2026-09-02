@echo off
setlocal
echo IMPORTANT:
echo Do NOT use locked TEST repeatedly for tuning.
echo Use a DEV/evaluation dataset first.
echo.
python -m eval.benchmark_v7_pipeline --dataset eval\datasets\v7_pipeline_dev_20.jsonl
endlocal
