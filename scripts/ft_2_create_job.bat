@echo off
setlocal
echo This step uploads data and CREATES A BILLABLE FINE-TUNING JOB.
echo Press Ctrl+C now if you only wanted to prepare the data.
pause

python -m training.upload_ft_files
if errorlevel 1 exit /b 1

python -m training.create_ft_job --model gpt-4.1-mini-2025-04-14 --suffix bci-gen-v7
if errorlevel 1 exit /b 1

echo.
echo Job created.
echo Dashboard: https://platform.openai.com/finetune
endlocal
