@echo off
rem Cuerpo que se ejecuta ya bajo la identidad de dominio (runas /netonly).
rem Llama a validate_codame.py y deja el resultado en validate_result.json.
rem NO recibe ni registra contrasenas.
setlocal
rem Resolver rutas relativas desde la raiz del repo (donde suele estar model.json)
cd /d "%~dp0..\..\"
set "PY=C:\Users\jabal\OtrosProyectos\proyecto_uniones\.venv\Scripts\python.exe"
set "SCRIPT=%~dp0validate_codame.py"
set "OUT=%~dp0validate_result.json"
set "LOG=%~dp0validate_result.log"
echo [%DATE% %TIME%] cwd=%CD% validate_codame.py %* > "%LOG%"
"%PY%" "%SCRIPT%" %* --out "%OUT%" >> "%LOG%" 2>&1
echo [%DATE% %TIME%] exit=%ERRORLEVEL% >> "%LOG%"
echo.
echo Resultado: %OUT%
echo Log      : %LOG%
