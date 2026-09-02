@echo off
setlocal
echo This creates a BILLABLE OpenAI fine-tuning job.
pause
python -m training_v2.upload_ft_files
if errorlevel 1 exit /b 1
python -m training_v2.create_ft_job
endlocal
