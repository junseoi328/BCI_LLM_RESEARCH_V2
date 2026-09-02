@echo off
setlocal
echo [1] Build semantic dataset
python -m training.build_dataset
if errorlevel 1 exit /b 1

echo [2] Validate semantic dataset
python -m training.validate_dataset
if errorlevel 1 exit /b 1

echo [3] Build phrase bank
python -m training.build_phrase_bank
if errorlevel 1 exit /b 1

echo [4] Export OpenAI SFT JSONL using CURRENT project generator prompt
python -m training.export_openai_sft
if errorlevel 1 exit /b 1

echo [5] Validate OpenAI JSONL
python -m training.validate_openai_sft
if errorlevel 1 exit /b 1

echo.
echo PREPARE COMPLETE
echo Review: training\data\train_review_v1.csv
echo Review: training\data\dev_review_v1.csv
endlocal
