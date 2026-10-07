<#
.SYNOPSIS
    Lanza Claude Code en modo no interactivo (solo lectura) y guarda su respuesta.

.DESCRIPTION
    Envoltorio sobre 'claude -p' para el bucle de revision automatica.

    Claude actua como REVISOR/ARBITRO: con --permission-mode plan y una lista blanca de
    herramientas de lectura (Read, Glob, Grep) no puede escribir en el proyecto. El unico
    escritor es el agente local.

    Ventaja frente a Codex en este equipo: Claude SI puede leer archivos, asi que no hay que
    pegarle el contexto; se le dan rutas y numeros de linea.

    El prompt va por STDIN como bytes UTF-8 (igual que en codex_revisar.ps1): la codificacion
    por defecto del stream de entrada seria la de consola (CP1252) y romperia los acentos.

.PARAMETER Entrada
    Archivo de texto con el prompt.

.PARAMETER Salida
    Donde guardar la respuesta. Por defecto: .revision\loop\respuesta_claude.md

.PARAMETER Modelo
    Fuerza un modelo (--model). Por defecto usa el de la cuenta.

.PARAMETER Herramientas
    Lista blanca de herramientas separadas por comas. Por defecto: Read,Glob,Grep

.PARAMETER TimeoutSeg
    Segundos maximos; al agotarse se mata el proceso. Por defecto 900.

.EXAMPLE
    .\claude_revisar.ps1 -Entrada .revision\loop\ronda_05_claude_arbitraje.md
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Entrada,
    [string]$Salida,
    [string]$Modelo,
    [string]$Herramientas = 'Read,Glob,Grep',
    [int]$TimeoutSeg = 900,
    [switch]$Silencioso
)

$ErrorActionPreference = 'Stop'

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LOOP = Join-Path $ROOT '.revision\loop'
$REG  = Join-Path $LOOP 'registro.md'

if (-not (Test-Path $LOOP)) { New-Item -ItemType Directory -Force -Path $LOOP | Out-Null }

function Ruta-Absoluta($r) {
    if ([System.IO.Path]::IsPathRooted($r)) { return $r }
    return (Join-Path $ROOT $r)
}

$Entrada = Ruta-Absoluta $Entrada
if (-not (Test-Path $Entrada)) { throw "No existe el archivo de entrada: $Entrada" }
if (-not $Salida) { $Salida = Join-Path $LOOP 'respuesta_claude.md' } else { $Salida = Ruta-Absoluta $Salida }

# ------------------------------------------------------------------ localizar Claude
# Se prefiere el ejecutable real: 'Get-Command claude' resuelve al shim claude.ps1, que
# ProcessStartInfo no puede lanzar directamente ("no es una aplicacion valida").
$cand = @(
    (Join-Path $env:APPDATA 'npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe'),
    (Join-Path $env:APPDATA 'npm\claude.cmd')
)
$cmd = Get-Command claude -ErrorAction SilentlyContinue
if ($cmd -and $cmd.Source -and $cmd.Source -notmatch '\.ps1$') { $cand += $cmd.Source }
$CLAUDE = $cand | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $CLAUDE) { throw ("No encuentro el CLI de Claude. Buscado en:`n  " + ($cand -join "`n  ")) }

$texto = [System.IO.File]::ReadAllText($Entrada, [System.Text.Encoding]::UTF8)

# ------------------------------------------------------------------ argumentos
$argsClaude = @('-p', '--output-format', 'text', '--permission-mode', 'plan')
if ($Herramientas) { $argsClaude += @('--allowedTools', $Herramientas) }
if ($Modelo)       { $argsClaude += @('--model', $Modelo) }

$argStr = ($argsClaude | ForEach-Object {
    if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
}) -join ' '

Write-Host ('Claude: {0}' -f (Split-Path -Leaf $CLAUDE)) -ForegroundColor DarkGray
Write-Host ('  prompt : {0} ({1} caracteres)' -f (Split-Path -Leaf $Entrada), $texto.Length) -ForegroundColor DarkGray
Write-Host ('  modelo : {0} | herramientas {1} | permiso plan (solo lectura)' -f $(if ($Modelo) { $Modelo } else { 'cuenta' }), $Herramientas) -ForegroundColor DarkGray
Write-Host ('  salida : {0}' -f $Salida) -ForegroundColor DarkGray
Write-Host '  revisando...' -ForegroundColor Cyan

# ------------------------------------------------------------------ ejecutar
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName               = $CLAUDE
$psi.Arguments              = $argStr
$psi.UseShellExecute        = $false
$psi.RedirectStandardInput  = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.WorkingDirectory       = $ROOT
$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$proc = [System.Diagnostics.Process]::Start($psi)
$tareaErr = $proc.StandardError.ReadToEndAsync()
# El prompt va como BYTES UTF-8 al stream base: StandardInput.Write() usa la codificacion
# de consola (CP1252 en Windows) y corrompe los acentos.
$bytesPrompt = [System.Text.Encoding]::UTF8.GetBytes($texto)
$proc.StandardInput.BaseStream.Write($bytesPrompt, 0, $bytesPrompt.Length)
$proc.StandardInput.BaseStream.Flush()
$proc.StandardInput.Close()
$salidaTxt = $proc.StandardOutput.ReadToEnd()
$expiro = -not $proc.WaitForExit($TimeoutSeg * 1000)
if ($expiro) { try { $proc.Kill() } catch { } }
$errTxt = ''
try { $errTxt = $tareaErr.Result } catch { }
$sw.Stop()

$codigo = $null
try { $codigo = $proc.ExitCode } catch { }

# ------------------------------------------------------------------ respuesta
if ($salidaTxt) {
    [System.IO.File]::WriteAllText($Salida, $salidaTxt, (New-Object System.Text.UTF8Encoding($false)))
}
$respuesta = ''
if (Test-Path $Salida) { $respuesta = [System.IO.File]::ReadAllText($Salida, [System.Text.Encoding]::UTF8).Trim() }

# ------------------------------------------------------------------ registrar
$estado = 'OK'
if ($expiro) { $estado = 'TIMEOUT' }
elseif ($codigo -ne 0) { $estado = "EXIT $codigo" }

$lineaReg = '| {0} | CLAUDE {1} | {2} | {3:N0} s | {4} | {5:N0} car. |' -f `
    (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), (Split-Path -Leaf $Entrada), $estado, $sw.Elapsed.TotalSeconds, (Split-Path -Leaf $Salida), $respuesta.Length
if (-not (Test-Path $REG)) {
    Set-Content -Path $REG -Value "# Registro del bucle de revision`r`n`r`n| Fecha | Prompt | Estado | Duracion | Respuesta | Tamano |`r`n| --- | --- | --- | --- | --- | --- |" -Encoding UTF8
}
Add-Content -Path $REG -Value $lineaReg -Encoding UTF8

# ------------------------------------------------------------------ resumen
Write-Host ''
if ($expiro) {
    Write-Host ('  TIMEOUT tras {0:N0} s (limite {1} s)' -f $sw.Elapsed.TotalSeconds, $TimeoutSeg) -ForegroundColor Red
} elseif ($codigo -ne 0) {
    Write-Host ('  FALLO: exit code {0} en {1:N0} s' -f $codigo, $sw.Elapsed.TotalSeconds) -ForegroundColor Red
} else {
    Write-Host ('  OK en {0:N0} s -> {1}' -f $sw.Elapsed.TotalSeconds, $Salida) -ForegroundColor Green
}
if ($errTxt) {
    $errUtil = @($errTxt -split "`r?`n" | Where-Object { $_ -and $_ -notmatch '^\s*$' })
    if ($errUtil.Count -gt 0) {
        Write-Host '  stderr:' -ForegroundColor Yellow
        $errUtil | Select-Object -First 8 | ForEach-Object { Write-Host ('    ' + $_) -ForegroundColor Yellow }
    }
}

if (-not $Silencioso -and $respuesta) {
    Write-Host ''
    Write-Host '--- respuesta de Claude ---' -ForegroundColor Cyan
    Write-Host $respuesta
}
