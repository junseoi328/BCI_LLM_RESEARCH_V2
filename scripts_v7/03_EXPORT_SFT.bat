@echo off
setlocal
python -m training_v2.export_openai_sft
if errorlevel 1 exit /b 1
python -m training_v2.validate_openai_sft
endlocal
