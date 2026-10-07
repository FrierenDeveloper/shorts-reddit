<#
.SYNOPSIS
    Lanza Codex en modo no interactivo (solo lectura) y guarda su respuesta.

.DESCRIPTION
    Envoltorio sobre 'codex exec' para el bucle de revision automatica.

    Codex actua como REVISOR: el sandbox es read-only, asi que nunca escribe en el
    proyecto. El unico escritor es el agente local. Eso elimina por diseno las
    carreras entre los dos agentes.

    El prompt se envia por STDIN y no como argumento, porque el brief de auditoria
    (~38 KB) supera el limite de linea de comandos de Windows (~32 KB).

    Cada ronda queda registrada en .revision\loop\registro.md.

.PARAMETER Entrada
    Archivo de texto con el prompt. Se envia por stdin.

.PARAMETER Salida
    Donde Codex deja su mensaje final (flag -o).
    Por defecto: .revision\loop\respuesta.md

.PARAMETER Modelo
    Fuerza un modelo (-m). Por defecto usa el de config.toml (gpt-6-sol).

.PARAMETER TimeoutSeg
    Segundos maximos; al agotarse se mata el proceso. Por defecto 900.

.PARAMETER Json
    Emite eventos JSONL (--json) en lugar del texto normal.

.PARAMETER Silencioso
    No imprime el cuerpo de la respuesta (solo el resumen). Util si se lee aparte.

.EXAMPLE
    .\codex_revisar.ps1 -Entrada .revision\loop\ronda_01_prompt.md

.EXAMPLE
    .\codex_revisar.ps1 -Entrada .revision\loop\revision.md -TimeoutSeg 300
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Entrada,
    [string]$Salida,
    # Por defecto: gpt-6-luna (barato y rapido) con esfuerzo bajo.
    # Se pasa como override por llamada, sin tocar ~\.codex\config.toml,
    # para no alterar la app de escritorio del usuario (gpt-6-sol / high).
    # Valores validos de esfuerzo en gpt-6-luna: low | medium | high | xhigh | max
    [string]$Modelo = 'gpt-6-luna',
    [string]$Esfuerzo = 'low',
    [int]$TimeoutSeg = 900,
    [switch]$Json,
    [string]$Sandbox = 'read-only',
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
if (-not $Salida) { $Salida = Join-Path $LOOP 'respuesta.md' } else { $Salida = Ruta-Absoluta $Salida }

# ------------------------------------------------------------------ localizar Codex
$candidatos = @(
    (Join-Path $env:USERPROFILE '.codex\.sandbox-bin\codex.exe'),
    (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin\faa963e871dd422c\codex.exe'),
    (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin\0ddb895c950eaeba\codex.exe')
)
$CODEX = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $CODEX) {
    throw ("No encuentro el ejecutable de Codex. Buscado en:`n  " + ($candidatos -join "`n  "))
}

$texto = [System.IO.File]::ReadAllText($Entrada, [System.Text.Encoding]::UTF8)

# ------------------------------------------------------------------ argumentos
$argsCodex = @('exec', '-C', $ROOT, '--skip-git-repo-check', '-s', $Sandbox,
               '--ephemeral', '--color', 'never')
if ($Json)   { $argsCodex += '--json' }
if ($Modelo) { $argsCodex += @('-m', $Modelo) }
# El valor se parsea como TOML: se entrecomilla para que quede como cadena literal.
if ($Esfuerzo) { $argsCodex += @('-c', ('model_reasoning_effort="{0}"' -f $Esfuerzo)) }
$argsCodex += @('-o', $Salida, '-')

# PowerShell 5.1 (.NET Framework) no tiene ProcessStartInfo.ArgumentList:
# hay que componer la cadena de argumentos a mano, entrecomillando lo que tenga espacios.
$argStr = ($argsCodex | ForEach-Object {
    if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
}) -join ' '

Write-Host ('Codex: {0}' -f (Split-Path -Leaf $CODEX)) -ForegroundColor DarkGray
Write-Host ('  prompt : {0} ({1} caracteres)' -f (Split-Path -Leaf $Entrada), $texto.Length) -ForegroundColor DarkGray
Write-Host ('  modelo : {0} | esfuerzo {1} | sandbox {2}' -f $Modelo, $Esfuerzo, $Sandbox) -ForegroundColor DarkGray
Write-Host ('  salida : {0}' -f $Salida) -ForegroundColor DarkGray
Write-Host '  revisando...' -ForegroundColor Cyan

# ------------------------------------------------------------------ ejecutar
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName               = $CODEX
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
# stderr se drena en paralelo: si no, el proceso puede bloquearse al llenarse el buffer
$tareaErr = $proc.StandardError.ReadToEndAsync()
# El prompt va como BYTES UTF-8 al stream base. StandardInput.Write() usa por defecto
# la codificacion de consola (CP1252 en Windows), con lo que los acentos se envian mal
# y Codex rechaza el prompt: "input is not valid UTF-8 (invalid byte at offset 8)".
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

# ------------------------------------------------------------------ limpiar ruido
# Codex escribe su banner y avisos por stderr. Se filtran para dejar a la vista
# solo lo que de verdad es un error.
$ruido = @(
    'Reading additional input from stdin',
    'Code Mode is unavailable',
    'code-mode-host',
    '^reasoning summaries:',
    '^reasoning effort:',
    '^OpenAI Codex v',
    '^-{4,}$',
    '^workdir:',
    '^model:',
    '^provider:',
    '^approval:',
    '^sandbox:',
    '^session id:',
    '^tokens used'
) -join '|'
$errUtil = @($errTxt -split "`r?`n" | Where-Object { $_ -and $_ -notmatch $ruido })

# ------------------------------------------------------------------ respuesta
$respuesta = ''
if (Test-Path $Salida) { $respuesta = [System.IO.File]::ReadAllText($Salida, [System.Text.Encoding]::UTF8).Trim() }

# ------------------------------------------------------------------ registrar
$estado = 'OK'
if ($expiro) { $estado = 'TIMEOUT' }
elseif ($codigo -ne 0) { $estado = "EXIT $codigo" }

$lineaReg = '| {0} | {1} | {2} | {3:N0} s | {4} | {5:N0} car. |' -f `
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
if ($errUtil.Count -gt 0) {
    Write-Host '  stderr:' -ForegroundColor Yellow
    $errUtil | Select-Object -First 10 | ForEach-Object { Write-Host ('    ' + $_) -ForegroundColor Yellow }
}

if (-not $Silencioso -and $respuesta) {
    Write-Host ''
    Write-Host '--- respuesta de Codex ---' -ForegroundColor Cyan
    Write-Host $respuesta
}
