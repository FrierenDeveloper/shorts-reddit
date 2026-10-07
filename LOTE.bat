@echo off
REM Lee links.txt: un link de Reddit (o posts\archivo.txt) por linea
cd /d "%~dp0"
echo Procesando links.txt ...
".venv\Scripts\python.exe" app\lote.py %*
pause
