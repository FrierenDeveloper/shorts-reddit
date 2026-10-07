@echo off
REM Abre la interfaz visual en el navegador (todo corre en tu PC)
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import gradio" 2>nul || (echo Instalando la interfaz por primera vez... & ".venv\Scripts\python.exe" -m pip install "gradio>=6" -q)
echo Abriendo la app en el navegador... (cierra esta ventana para apagarla)
".venv\Scripts\python.exe" app\interfaz.py
pause
