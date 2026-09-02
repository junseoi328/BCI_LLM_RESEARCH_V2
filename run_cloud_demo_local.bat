@echo off
cd /d %~dp0

call .venv\Scripts\activate

set MOCK_MODE=false
set BCI_DEMO_MODE=true
set LOCAL_BCI_GENERATOR_ENABLED=false

echo =====================================================
echo  E-SIM-JEON-SIM BCI Speller - Production-like Demo
echo =====================================================
echo.
echo URL: http://127.0.0.1:8002/speller
echo.

start http://127.0.0.1:8002/speller
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
