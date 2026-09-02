@echo off
setlocal
echo This calls the CURRENT OpenAI generator and uses API credits.
pause
python -m training_v2.teacher_augment
endlocal
