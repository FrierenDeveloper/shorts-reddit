@echo off
REM Borra cache y temporales; pregunta antes de borrar videos ya publicados y archivos viejos
cd /d "%~dp0"
".venv\Scripts\python.exe" app\limpiar.py %*
pause
