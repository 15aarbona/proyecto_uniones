@echo off
rem ---------------------------------------------------------------------------
rem Ejecuta el modulo de validacion (validation.codame) bajo runas /netonly.
rem La contrasena la pide runas de forma interactiva: este script no la maneja.
rem
rem Uso:
rem   run_codame.cmd ad.tecnicasreunidas.es\<usuario> --csv resultado_v_pru.csv --out ratios.csv
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
set "SCRIPTDIR=%~dp0"
set "ROOT=%SCRIPTDIR%.."
set "LOGB=%SCRIPTDIR%run_codame.log"
if "%~1"=="" goto usage
set "USERDOM=%~1"
shift
set "REST="
:parse
if "%~1"=="" goto run
set "REST=%REST% %1"
shift
goto parse
:run
echo [%DATE% %TIME%] user=%USERDOM% rest=%REST% > "%LOGB%"
runas /netonly /user:%USERDOM% "cmd /c cd /d %ROOT% && .venv\Scripts\python.exe -m validation.codame%REST% >> validation\run_codame.log 2>&1"
echo [%DATE% %TIME%] runas exit=%ERRORLEVEL% >> "%LOGB%"
echo.
echo Log: %SCRIPTDIR%run_codame.log
goto :eof
:usage
echo Uso: run_codame.cmd ^<DOMINIO\usuario^> --csv f.csv --out ratios.csv [--chunk N]
endlocal
exit /b 1
