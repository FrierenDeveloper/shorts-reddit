@echo off
REM Igual que LOTE.bat, con la voz de Chatterbox
cd /d "%~dp0"
set SHORTS_MOTOR_VOZ=chatterbox
echo Procesando links.txt con Chatterbox ...
".venv\Scripts\python.exe" app\lote.py %*
pause
