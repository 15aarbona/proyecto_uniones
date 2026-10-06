@echo off
rem ---------------------------------------------------------------------------
rem Lanza la prueba SQL con runas /netonly usando una cuenta de dominio.
rem NO requiere que la cuenta exista en este equipo.
rem
rem Uso:
rem    run_as_netonly.cmd ad.tecnicasreunidas.es\<usuario>
rem
rem Pedira la contrasena de la cuenta de dominio. El resultado queda en
rem    <esta carpeta>\sql_test_result.txt
rem ---------------------------------------------------------------------------
setlocal
if "%~1"=="" (
    echo Uso: run_as_netonly.cmd ^<DOMINIO\usuario^>
    echo Ej.: run_as_netonly.cmd ad.tecnicasreunidas.es^\%USERNAME%
    exit /b 1
)
echo Lanzando prueba SQL como "%~1" (runas /netonly)...
echo Te pedira la contrasena de la cuenta de dominio.
runas /netonly /user:%~1 "cmd /c %~dp0run_test_netonly.cmd"
endlocal
