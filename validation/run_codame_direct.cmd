@echo off
rem ---------------------------------------------------------------------------
rem Ejecuta el modulo de validacion SIN runas (para usuarios que YA tienen
rem acceso al SQL con su cuenta de Windows actual: equipo unido al dominio o
rem credencial guardada con cmdkey).
rem
rem Uso:
rem   run_codame_direct.cmd --csv resultado_v_pru.csv --out ratios.csv
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m validation.codame %*
