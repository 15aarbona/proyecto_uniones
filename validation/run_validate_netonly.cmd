@echo off
rem ---------------------------------------------------------------------------
rem Valida un diseno con CODAME ejecutando validate_codame.py bajo runas /netonly.
rem La contrasena la pide runas de forma interactiva: este script no la maneja.
rem
rem Uso:
rem    run_validate_netonly.cmd ad.tecnicasreunidas.es\<usuario> --row 1 --model-json model.json
rem    run_validate_netonly.cmd ad.tecnicasreunidas.es\<usuario> --no-runas --row 1   (sin runas)
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
set "SCRIPTDIR=%~dp0"
set "BODY=%SCRIPTDIR%validate_netonly_body.cmd"
set "LOGB=%SCRIPTDIR%wrapper.log"

if "%~1"=="" goto usage
set "USERDOM=%~1"
shift
set "NORUNAS="
set "REST="

:parse
if "%~1"=="" goto run
if /I "%~1"=="--no-runas" set "NORUNAS=1"
if /I not "%~1"=="--no-runas" set "REST=%REST% %1"
shift
goto parse

:run
echo [%DATE% %TIME%] user=%USERDOM% norunas=%NORUNAS% rest=%REST% > "%LOGB%"
if defined NORUNAS goto norunas

echo Lanzando validacion como "%USERDOM%" (runas /netonly)...
echo comando: runas /netonly /user:%USERDOM% "cmd /c %BODY% %REST%" >> "%LOGB%"
runas /netonly /user:%USERDOM% "cmd /c %BODY% %REST%"
echo [%DATE% %TIME%] runas exit=%ERRORLEVEL% >> "%LOGB%"
goto end

:norunas
echo Modo --no-runas: ejecutando como usuario actual...
call "%BODY%" %REST%
echo [%DATE% %TIME%] exit=%ERRORLEVEL% >> "%LOGB%"
goto end

:end
echo.
echo Wrapper log : %LOGB%
echo Resultado   : %SCRIPTDIR%validate_result.json
echo Log detalle : %SCRIPTDIR%validate_result.log
endlocal
goto :eof

:usage
echo Uso: run_validate_netonly.cmd ^<DOMINIO\usuario^> [^--row N^] [^--model-json f.json^] [^--no-runas^]
endlocal
exit /b 1
