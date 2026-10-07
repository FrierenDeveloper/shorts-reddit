# Instalador de Shorts Reddit (Windows). Ejecutar en PowerShell dentro de esta carpeta:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # carpeta del proyecto (los scripts viven en app\)
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

if (-not (Have python)) {
  Write-Host "Instalando Python 3.12..." -ForegroundColor Cyan
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
}
if (-not (Have ffmpeg)) {
  Write-Host "Instalando FFmpeg..." -ForegroundColor Cyan
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
}
# refrescar PATH en esta sesión
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r app\requirements.txt

Write-Host "`nComprobando..." -ForegroundColor Cyan
ffmpeg -version | Select-Object -First 1
.\.venv\Scripts\python.exe -c "import edge_tts, faster_whisper, numpy, PIL, soundfile, openai; print('Librerias OK')"
Write-Host "`nListo. Prueba:  CREAR_SHORT.bat (arrastra encima un JSON de historias\)" -ForegroundColor Green
