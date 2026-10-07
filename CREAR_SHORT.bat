@echo off
REM Arrastra uno o varios JSON de historias\ sobre este archivo
cd /d "%~dp0"
".venv\Scripts\python.exe" app\make_short.py %*
pause
