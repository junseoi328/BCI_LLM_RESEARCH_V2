@echo off
setlocal
python -m training_v2.finalize_dataset --review training_v2\reviews\teacher_candidate_review.csv
if errorlevel 1 exit /b 1
python -m training_v2.validate_dataset
if errorlevel 1 exit /b 1
python -m training_v2.dataset_stats
endlocal
