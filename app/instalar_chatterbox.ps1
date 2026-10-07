# Instala Chatterbox Multilingual V3 (voz local con clonación, licencia MIT) en un entorno aparte (.venv_cb, Python 3.11).
# Requiere haber ejecutado antes INSTALAR.bat. Descarga ~4 GB (PyTorch + modelo).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # carpeta del proyecto (los scripts viven en app\)

$has311 = $false
try { py -3.11 --version | Out-Null; $has311 = ($LASTEXITCODE -eq 0) } catch {}
if (-not $has311) {
  Write-Host "Instalando Python 3.11 (Chatterbox está probado en esa versión)..." -ForegroundColor Cyan
  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}

if (-not (Test-Path .venv_cb)) { py -3.11 -m venv .venv_cb }
$py = ".\.venv_cb\Scripts\python.exe"
& $py -m pip install --upgrade pip

Write-Host "1/3 PyTorch con CUDA para la RTX..." -ForegroundColor Cyan
& $py -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

Write-Host "2/3 Chatterbox..." -ForegroundColor Cyan
& $py -m pip install --upgrade --force-reinstall --no-deps "git+https://github.com/resemble-ai/chatterbox.git"
if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar Chatterbox desde el repositorio oficial." }

Write-Host "3/3 Descargando el modelo multilingüe (una sola vez)..." -ForegroundColor Cyan
& $py -c "import torch; from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M; M.from_pretrained(device='cuda' if torch.cuda.is_available() else 'cpu', t3_model='v3'); print('Modelo: Multilingual V3 | CUDA:', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw "No se pudo cargar Chatterbox Multilingual V3." }

New-Item -ItemType Directory -Force voces | Out-Null
Write-Host "`nListo. Usa CREAR_SHORT_CHATTERBOX.bat o LOTE_CHATTERBOX.bat." -ForegroundColor Green
Write-Host "Opcional: pon tu voz en voces\narrador.wav (10-15 s, sin ruido) para clonarla." -ForegroundColor Green
