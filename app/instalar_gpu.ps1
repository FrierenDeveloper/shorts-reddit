# Extras para NVIDIA (RTX): render en GPU (PyTorch CUDA), Whisper en GPU y voces locales (Kokoro / XTTS).
# Ejecutar DESPUÉS de instalar.ps1:   powershell -ExecutionPolicy Bypass -File .\instalar_gpu.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # carpeta del proyecto (los scripts viven en app\)
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Primero ejecuta INSTALAR.bat" -ForegroundColor Red; exit 1 }

Write-Host "1/4 PyTorch con CUDA (~2.5 GB)..." -ForegroundColor Cyan
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cu124

Write-Host "2/4 Kokoro (voz local) + ONNX Runtime GPU..." -ForegroundColor Cyan
& $py -m pip install kokoro-onnx onnxruntime-gpu transformers
& $py -m pip uninstall -y onnxruntime 2>$null
& $py -m pip install --force-reinstall --no-deps onnxruntime-gpu

Write-Host "3/4 Modelos de Kokoro (~350 MB)..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force app\modelos | Out-Null
$R = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
if (-not (Test-Path app\modelos\kokoro-v1.0.onnx)) { Invoke-WebRequest "$R/kokoro-v1.0.onnx" -OutFile app\modelos\kokoro-v1.0.onnx }
if (-not (Test-Path app\modelos\voices-v1.0.bin))  { Invoke-WebRequest "$R/voices-v1.0.bin"  -OutFile app\modelos\voices-v1.0.bin }

Write-Host "4/4 XTTS v2 (clonación de voz, opcional)..." -ForegroundColor Cyan
try { & $py -m pip install coqui-tts } catch { Write-Host "XTTS no se pudo instalar (opcional, puedes ignorarlo)." -ForegroundColor Yellow }

Write-Host "`nComprobando GPU..." -ForegroundColor Cyan
& $py -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
& $py -c "import os,torch,pathlib; os.add_dll_directory(str(pathlib.Path(torch.__file__).parent/'lib')); import onnxruntime as o; print('ONNX:', o.get_available_providers())"
ffmpeg -hide_banner -encoders 2>$null | Select-String nvenc
Write-Host "`nListo. make_short.py usará la GPU automáticamente." -ForegroundColor Green
