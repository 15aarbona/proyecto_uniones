@echo off
rem ---------------------------------------------------------------------------
rem Ejecuta test_sql_connection.ps1 y guarda toda la salida en un log,
rem pensado para lanzarse con:  runas /netonly /user:DOMINIO\usuario "cmd /c <este .cmd>"
rem (la ventana de runas se cierra sola; el resultado queda en sql_test_result.txt)
rem ---------------------------------------------------------------------------
setlocal
set "PS=%~dp0test_sql_connection.ps1"
set "LOG=%~dp0sql_test_result.txt"
echo [%DATE% %TIME%] ejecutando "%PS%" %* > "%LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%" %* >> "%LOG%" 2>&1
echo [%DATE% %TIME%] fin (exit=%ERRORLEVEL%) >> "%LOG%"
echo.
echo Resultado guardado en: %LOG%
