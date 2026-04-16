@echo off
echo.
echo ========================================
echo   DailyAgent 2.0 - Server
echo ========================================
echo.
echo Iniciando servidor com API + Monitor...
echo.

cd /d "%~dp0"

REM Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo ERRO: Ambiente virtual nao encontrado!
    echo Execute: python -m venv .venv
    echo         .venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

REM Inicia o servidor
.venv\Scripts\python.exe server.py %*

pause
