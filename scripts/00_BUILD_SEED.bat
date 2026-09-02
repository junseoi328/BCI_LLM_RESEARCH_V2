@echo off
setlocal
python -m training_v2.build_seed_pool
if errorlevel 1 exit /b 1
python -m training_v2.dataset_stats
echo.
echo Seed pool generated.
echo Review: training_v2\reviews\candidate_pool_review_v2.csv
endlocal
