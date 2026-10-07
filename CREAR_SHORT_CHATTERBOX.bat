@echo off
REM Igual que CREAR_SHORT.bat, con la voz de Chatterbox (local, GPU)
cd /d "%~dp0"
set SHORTS_MOTOR_VOZ=chatterbox
".venv\Scripts\python.exe" app\make_short.py %*
pause
