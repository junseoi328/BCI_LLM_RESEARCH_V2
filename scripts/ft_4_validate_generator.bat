@echo off
setlocal
python -m training.smoke_ft_model
if errorlevel 1 exit /b 1

python -m eval.compare_generator_base_vs_ft
endlocal
