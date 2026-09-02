@echo off
setlocal EnableExtensions

echo ============================================================
echo   BCI_LLM_RESEARCH_V2 - Render Deployment Merge
echo ============================================================
echo.

REM ============================================================
REM 1. PROJECT PATH
REM ============================================================

set "PROJECT=C:\Users\User\Desktop\BCI_LLM_RESEARCH_V2"

REM 다운로드한 ZIP 위치
set "ZIP=%USERPROFILE%\Downloads\BCI_RENDER_DEPLOY_FINAL.zip"

REM 임시 압축 해제 위치
set "TEMP_DIR=%TEMP%\BCI_RENDER_DEPLOY_FINAL"

REM 백업 폴더
set "BACKUP=%PROJECT%\backup_before_render_merge"


echo [1/8] Project:
echo %PROJECT%
echo.

echo [2/8] ZIP:
echo %ZIP%
echo.


REM ============================================================
REM 2. ZIP EXIST CHECK
REM ============================================================

if not exist "%ZIP%" (
    echo.
    echo [ERROR] ZIP file not found:
    echo %ZIP%
    echo.
    echo BCI_RENDER_DEPLOY_FINAL.zip 파일을
    echo Downloads 폴더에 넣은 뒤 다시 실행하세요.
    echo.
    pause
    exit /b 1
)


REM ============================================================
REM 3. PROJECT EXIST CHECK
REM ============================================================

if not exist "%PROJECT%\app" (
    echo.
    echo [ERROR] app folder not found.
    echo PROJECT path:
    echo %PROJECT%
    echo.
    pause
    exit /b 1
)


cd /d "%PROJECT%"


REM ============================================================
REM 4. BACKUP IMPORTANT FILES
REM ============================================================

echo [3/8] Creating backup...

if not exist "%BACKUP%" (
    mkdir "%BACKUP%"
)

if exist "app\main.py" (
    copy /Y "app\main.py" "%BACKUP%\main.py" >nul
)

if exist "app\pipeline\service.py" (
    copy /Y "app\pipeline\service.py" "%BACKUP%\service.py" >nul
)

if exist "app\llm\factory.py" (
    copy /Y "app\llm\factory.py" "%BACKUP%\factory.py" >nul
)

if exist "app\llm\factory_final.py" (
    copy /Y "app\llm\factory_final.py" "%BACKUP%\factory_final.py" >nul
)

if exist "app\llm\mock_client.py" (
    copy /Y "app\llm\mock_client.py" "%BACKUP%\mock_client.py" >nul
)

if exist ".gitignore" (
    copy /Y ".gitignore" "%BACKUP%\.gitignore" >nul
)

echo Backup complete:
echo %BACKUP%
echo.


REM ============================================================
REM 5. CLEAR TEMP
REM ============================================================

echo [4/8] Preparing temporary directory...

if exist "%TEMP_DIR%" (
    rmdir /S /Q "%TEMP_DIR%"
)

mkdir "%TEMP_DIR%"


REM ============================================================
REM 6. EXTRACT ZIP
REM ============================================================

echo [5/8] Extracting deployment ZIP...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TEMP_DIR%' -Force"

if errorlevel 1 (
    echo.
    echo [ERROR] ZIP extraction failed.
    pause
    exit /b 1
)

echo Extraction complete.
echo.


REM ============================================================
REM 7. MERGE INTO EXISTING PROJECT
REM ============================================================

echo [6/8] Merging deployment files into project...
echo.

robocopy "%TEMP_DIR%" "%PROJECT%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP

REM Robocopy return codes 0~7 are normal/success states.
if errorlevel 8 (
    echo.
    echo [ERROR] Robocopy merge failed.
    echo Check backup:
    echo %BACKUP%
    pause
    exit /b 1
)

echo.
echo Merge complete.
echo.


REM ============================================================
REM 8. MAKE SURE .ENV IS NOT COMMITTED
REM ============================================================

echo [7/8] Updating .gitignore...

findstr /X /C:".env" ".gitignore" >nul 2>&1
if errorlevel 1 echo .env>>.gitignore

findstr /X /C:".env.*" ".gitignore" >nul 2>&1
if errorlevel 1 echo .env.*>>.gitignore

findstr /X /C:"!.env.production.example" ".gitignore" >nul 2>&1
if errorlevel 1 echo !.env.production.example>>.gitignore

findstr /X /C:"local_models/" ".gitignore" >nul 2>&1
if errorlevel 1 echo local_models/>>.gitignore

findstr /X /C:"local_ft/" ".gitignore" >nul 2>&1
if errorlevel 1 echo local_ft/>>.gitignore

findstr /X /C:"__pycache__/" ".gitignore" >nul 2>&1
if errorlevel 1 echo __pycache__/>>.gitignore

findstr /X /C:"*.pyc" ".gitignore" >nul 2>&1
if errorlevel 1 echo *.pyc>>.gitignore


REM ============================================================
REM 9. CHECK EXPECTED FILES
REM ============================================================

echo.
echo [8/8] Checking deployment files...
echo.

if exist "render.yaml" (
    echo [OK] render.yaml
) else (
    echo [FAIL] render.yaml
)

if exist "Dockerfile" (
    echo [OK] Dockerfile
) else (
    echo [FAIL] Dockerfile
)

if exist "requirements.deploy.txt" (
    echo [OK] requirements.deploy.txt
) else (
    echo [FAIL] requirements.deploy.txt
)

if exist "app\static\bci_speller.html" (
    echo [OK] app\static\bci_speller.html
) else (
    echo [FAIL] app\static\bci_speller.html
)

if exist "app\api\speller_ui.py" (
    echo [OK] app\api\speller_ui.py
) else (
    echo [FAIL] app\api\speller_ui.py
)

if exist "app\llm\demo_resilient_client.py" (
    echo [OK] app\llm\demo_resilient_client.py
) else (
    echo [FAIL] app\llm\demo_resilient_client.py
)

if exist "scripts\start_prod.py" (
    echo [OK] scripts\start_prod.py
) else (
    echo [FAIL] scripts\start_prod.py
)


REM ============================================================
REM CLEAN TEMP
REM ============================================================

if exist "%TEMP_DIR%" (
    rmdir /S /Q "%TEMP_DIR%"
)


echo.
echo ============================================================
echo   MERGE COMPLETE
echo ============================================================
echo.
echo Project:
echo %PROJECT%
echo.
echo Backup:
echo %BACKUP%
echo.
echo NEXT COMMAND:
echo python -m py_compile app\main.py
echo.
echo ============================================================

pause