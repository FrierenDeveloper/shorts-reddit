<#
.SYNOPSIS
    Genera el bloque de sincronización para pegar en ChatGPT.

.DESCRIPTION
    Compara el código actual con el snapshot .revision\base\, corre mediciones
    baratas (sin renderizar vídeo ni gastar créditos de API) y produce
    .revision\bloque.md con todo lo que ChatGPT necesita para saber sobre qué
    versión del código está opinando.

    No modifica absolutamente nada del proyecto: solo lee y escribe en .revision\.

.PARAMETER Diff
    Incluye el diff completo de cada archivo cambiado, no solo el resumen.

.PARAMETER SinPortapapeles
    No copia el resultado al portapapeles.

.PARAMETER MaxLineasDiff
    Tope de líneas de diff por archivo (por defecto 500).

.EXAMPLE
    .\sincronizar.ps1
    Genera el bloque y lo copia al portapapeles. Pegar en ChatGPT.

.EXAMPLE
    .\sincronizar.ps1 -Diff
    Igual, pero con el diff completo (útil cuando ya hay parches aplicados).
#>
[CmdletBinding()]
param(
    [switch]$Diff,
    [switch]$SinPortapapeles,
    [int]$MaxLineasDiff = 500
)

$ErrorActionPreference = 'Stop'

# ------------------------------------------------------------------ rutas
# Nota: nombres sin ambiguedad a proposito. $ARCHIVO_BLOQUE es el .md que
# genera ESTE script; $DIR_SALIDA es la carpeta salida\ del proyecto.
$ROOT           = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DIR_REVISION   = Join-Path $ROOT '.revision'
$DIR_BASE       = Join-Path $DIR_REVISION 'base'
$ARCHIVO_HASHES = Join-Path $DIR_REVISION 'hashes_base.json'
$ARCHIVO_BLOQUE = Join-Path $DIR_REVISION 'bloque.md'
$ARCHIVO_ESTADO = Join-Path $ROOT 'REVISION_ESTADO.md'
$DIR_SALIDA     = Join-Path $ROOT 'salida'
$DIR_CACHE      = Join-Path $ROOT 'cache'

# ------------------------------------------------------------------ utilidades
function Leer-Texto($ruta) {
    if ($ruta -and (Test-Path $ruta)) {
        return [System.IO.File]::ReadAllText($ruta, [System.Text.Encoding]::UTF8)
    }
    return ''
}

function Escribir-SinBom($ruta, $texto) {
    $dir = Split-Path -Parent $ruta
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ruta, $texto, $enc)
}

function Get-Seguidos {
    $lista = @()
    $appDir = Join-Path $ROOT 'app'
    if (Test-Path $appDir) {
        $lista += Get-ChildItem -Path $appDir -Recurse -File |
                  Where-Object { $_.FullName -notmatch '\\__pycache__\\' }
    }
    # README.md y .gitignore tambien se mantienen: si no se siguen, sus cambios no salen en
    # el diff y el revisor no se entera de que existen.
    foreach ($extra in @('README.md', '.gitignore')) {
        $f = Join-Path $ROOT $extra
        if (Test-Path $f) { $lista += Get-Item -Path $f }
    }
    return $lista
}

function Relativo($rutaCompleta) {
    return ($rutaCompleta.Substring($ROOT.Length + 1) -replace '\\', '/')
}

$sb = New-Object System.Text.StringBuilder
function Add-Linea($texto) { [void]$sb.AppendLine([string]$texto) }

# ------------------------------------------------------------------ 1. hashes
Write-Host 'Comparando con el snapshot...' -ForegroundColor Cyan

$actuales = @{}
foreach ($f in Get-Seguidos) {
    $rel = Relativo $f.FullName
    $actuales[$rel] = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash.ToLower()
}

$previos = @{}
if (Test-Path $ARCHIVO_HASHES) {
    $json = Leer-Texto $ARCHIVO_HASHES | ConvertFrom-Json
    foreach ($prop in $json.PSObject.Properties) { $previos[$prop.Name] = $prop.Value }
} else {
    Write-Host '  AVISO: no hay .revision\hashes_base.json; no puedo detectar cambios.' -ForegroundColor Yellow
}

$modificados = @(); $anadidos = @(); $borrados = @()
foreach ($k in $actuales.Keys) {
    if (-not $previos.ContainsKey($k)) { $anadidos += $k }
    elseif ($previos[$k] -ne $actuales[$k]) { $modificados += $k }
}
foreach ($k in $previos.Keys) {
    if (-not $actuales.ContainsKey($k)) { $borrados += $k }
}
$modificados = @($modificados | Sort-Object)
$anadidos    = @($anadidos    | Sort-Object)
$borrados    = @($borrados    | Sort-Object)

$hayCambios = (($modificados.Count + $anadidos.Count + $borrados.Count) -gt 0)

# ------------------------------------------------------------------ 2. mediciones
Write-Host 'Midiendo el estado real...' -ForegroundColor Cyan

function Get-SampleRates {
    $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
    if (-not $ffprobe) { return [pscustomobject]@{ error = 'ffprobe no esta en el PATH' } }
    $mp4s = @()
    if (Test-Path $DIR_SALIDA) {
        $mp4s = @(Get-ChildItem -Path $DIR_SALIDA -Recurse -File -Filter *.mp4)
    }
    if ($mp4s.Count -eq 0) { return [pscustomobject]@{ error = 'no hay .mp4 en salida\' } }
    $rates = @()
    foreach ($archivo in $mp4s) {
        try {
            $sr = & ffprobe -v error -select_streams a -show_entries stream=sample_rate -of csv=p=0 $archivo.FullName 2>$null
            if ($sr) { $rates += ([string]($sr | Select-Object -First 1)).Trim() }
        } catch { }
    }
    return [pscustomobject]@{ rates = $rates; total = $mp4s.Count }
}

$med = @{}

$med['sample_rates'] = Get-SampleRates

# fugas de temporales
$med['fugas'] = 0
if (Test-Path $DIR_CACHE) {
    $med['fugas'] = @(Get-ChildItem -Path $DIR_CACHE -Recurse -File -Include '_prep_*', '*.download' -ErrorAction SilentlyContinue).Count
}

# __pycache__ dentro de los venv
$pycVenv = 0
foreach ($v in @('.venv', '.venv_cb')) {
    $vd = Join-Path $ROOT $v
    if (Test-Path $vd) {
        $pycVenv += @(Get-ChildItem -Path $vd -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue).Count
    }
}
$med['pycache_venv'] = $pycVenv

# tamano de cache
$med['cache_mb'] = 0
if (Test-Path $DIR_CACHE) {
    $suma = (Get-ChildItem -Path $DIR_CACHE -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if ($suma) { $med['cache_mb'] = [math]::Round($suma / 1MB, 1) }
}

# claves.json cubierto por .gitignore?
$gi = Leer-Texto (Join-Path $ROOT '.gitignore')
$med['claves_ignorada'] = ($gi -match 'claves\.json')

# recuento de salidas
$med['n_mp4'] = 0
if (Test-Path $DIR_SALIDA) {
    $med['n_mp4'] = @(Get-ChildItem -Path $DIR_SALIDA -Recurse -File -Filter *.mp4).Count
}

# ------------------------------------------------------------------ 3. diff
$resumenDiff = @{}
$diffCompleto = ''
if ($hayCambios) {
    $git = Get-Command git -ErrorAction SilentlyContinue
    # git escribe avisos por stderr (p. ej. LF/CRLF) y en PowerShell 5.1, con
    # ErrorActionPreference='Stop', eso se convierte en error terminante que aborta
    # el script. Se aisla aqui y se desactivan los avisos de conversion de saltos.
    $eapPrevio = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $gitOpts = @('-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false', '-c', 'core.quotepath=false')
    try {
        foreach ($rel in @($modificados + $anadidos)) {
            $rutaBase = Join-Path $DIR_BASE ($rel -replace '/', '\')
            if (-not (Test-Path $rutaBase)) { $resumenDiff[$rel] = 'nuevo (no estaba en el snapshot)'; continue }
            if (-not $git) { $resumenDiff[$rel] = 'git no disponible'; continue }
            # rutas relativas (con -C) para que el encabezado del diff salga legible
            $relBase = ".revision/base/$rel"
            $num = @(& git -C $ROOT @gitOpts diff --no-index --numstat -- $relBase $rel 2>$null)
            if ($num.Count -gt 0 -and $num[0]) {
                $partes = @([string]$num[0] -split "`t")
                if ($partes.Count -ge 2) {
                    $resumenDiff[$rel] = ('+{0} / -{1} lineas' -f $partes[0], $partes[1])
                } else {
                    $resumenDiff[$rel] = 'cambio detectado'
                }
            } else {
                $resumenDiff[$rel] = 'sin diferencias de texto (¿binario?)'
            }
            if ($Diff) {
                $d = @(& git -C $ROOT @gitOpts diff --no-index --unified=2 -- $relBase $rel 2>$null)
                if ($d.Count -gt 0) {
                    if ($d.Count -gt $MaxLineasDiff) {
                        $d = @($d[0..($MaxLineasDiff - 1)]) + @("... (diff truncado a $MaxLineasDiff lineas)")
                    }
                    $diffCompleto += ("`r`n### {0}`r`n``````diff`r`n{1}`r`n```````r`n" -f $rel, ($d -join "`r`n"))
                }
            }
        }
    } finally {
        $ErrorActionPreference = $eapPrevio
    }
}

# ------------------------------------------------------------------ 4. pendientes
$estadoTexto = Leer-Texto $ARCHIVO_ESTADO
$pendientes = @()
foreach ($linea in ($estadoTexto -split "`r?`n")) {
    if ($linea -match '^\|\s*\d+\s*\|\s*(.+?)\s*\|') {
        $candidata = $matches[1]
        if ($linea -match '`pendiente`') {
            if ($candidata.Length -gt 140) { $candidata = $candidata.Substring(0, 140) + '...' }
            $pendientes += $candidata
        }
    }
}

# ------------------------------------------------------------------ 5. componer
Add-Linea '# BLOQUE DE SINCRONIZACIÓN — `shorts-reddit`'
Add-Linea ''
Add-Linea ('Generado: **{0}** por `sincronizar.ps1`.' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Add-Linea ''
Add-Linea 'Instrucciones para ChatGPT: este bloque sustituye a cualquier copia anterior del'
Add-Linea 'código que hayas visto. Si un archivo aparece como MODIFICADO, **tu análisis previo'
Add-Linea 'de ese archivo ya no es válido**: pide el fragmento actualizado antes de escribir un'
Add-Linea 'parche sobre él. El brief completo de hallazgos es `REVISION_IA.md`.'
Add-Linea ''
Add-Linea '---'
Add-Linea ''

Add-Linea '## 1. ¿Sigue vigente tu revisión?'
Add-Linea ''
if (-not $hayCambios) {
    Add-Linea ('**SÍ, sin cambios.** El código está idéntico al snapshot que revisaste: **{0} archivos** verificados por SHA256.' -f $actuales.Count)
} else {
    Add-Linea ('**NO.** Hay cambios desde el snapshot: **{0} modificados, {1} añadidos, {2} borrados** (sobre {3} archivos seguidos).' -f $modificados.Count, $anadidos.Count, $borrados.Count, $actuales.Count)
}
Add-Linea ''
if ($modificados.Count -gt 0) {
    Add-Linea '### Archivos MODIFICADOS (tu análisis previo queda obsoleto)'
    Add-Linea ''
    Add-Linea '| Archivo | Cambio |'
    Add-Linea '| --- | --- |'
    foreach ($k in $modificados) {
        $r = ''
        if ($resumenDiff.ContainsKey($k)) { $r = $resumenDiff[$k] }
        Add-Linea ('| `{0}` | {1} |' -f $k, $r)
    }
    Add-Linea ''
}
if ($anadidos.Count -gt 0) {
    Add-Linea '### Archivos NUEVOS (no los has visto nunca)'
    Add-Linea ''
    foreach ($k in $anadidos) { Add-Linea ('- `{0}`' -f $k) }
    Add-Linea ''
}
if ($borrados.Count -gt 0) {
    Add-Linea '### Archivos BORRADOS'
    Add-Linea ''
    foreach ($k in $borrados) { Add-Linea ('- `{0}`' -f $k) }
    Add-Linea ''
}
Add-Linea '### Hashes actuales de los archivos de código'
Add-Linea ''
Add-Linea '| Archivo | SHA256 (primeros 16) |'
Add-Linea '| --- | --- |'
foreach ($k in @($actuales.Keys | Sort-Object)) {
    if ($k -match '\.(py|ps1|md)$') {
        Add-Linea ('| `{0}` | `{1}` |' -f $k, $actuales[$k].Substring(0, 16))
    }
}
Add-Linea ''
Add-Linea '---'
Add-Linea ''

if ($Diff -and $diffCompleto -ne '') {
    Add-Linea '## 2. Diff completo desde el snapshot'
    Add-Linea ''
    Add-Linea $diffCompleto
    Add-Linea '---'
    Add-Linea ''
}

Add-Linea '## 3. Estado de la revisión'
Add-Linea ''
if ($estadoTexto -ne '') {
    Add-Linea '_(contenido de `REVISION_ESTADO.md`)_'
    Add-Linea ''
    Add-Linea $estadoTexto
} else {
    Add-Linea '_No se encontró `REVISION_ESTADO.md`._'
}
Add-Linea ''
Add-Linea '---'
Add-Linea ''

Add-Linea '## 4. Mediciones en vivo'
Add-Linea ''
Add-Linea '| Comprobación | Valor actual | Esperado |'
Add-Linea '| --- | --- | --- |'
$sr = $med['sample_rates']
if ($sr.PSObject.Properties.Name -contains 'error') {
    Add-Linea ('| Sample rate del audio | no medido ({0}) | 48000 Hz |' -f $sr.error)
} else {
    $unicos = (@($sr.rates | Sort-Object -Unique) -join ', ')
    Add-Linea ('| Sample rate del audio | **{0} Hz** | 48000 Hz |' -f $unicos)
    Add-Linea ('| Vídeos analizados | {0} | — |' -f $sr.total)
}
Add-Linea ('| Ficheros temporales fugados (`_prep_*`, `*.download`) | {0} | 0 |' -f $med['fugas'])
Add-Linea ('| Directorios `__pycache__` dentro de `.venv*` | {0} | se conservan (I7 sin arreglar) |' -f $med['pycache_venv'])
Add-Linea ('| Tamaño de `cache\` | {0} MB | — |' -f $med['cache_mb'])
if ($med['claves_ignorada']) {
    Add-Linea '| `claves.json` cubierto por `.gitignore` | sí | sí |'
} else {
    Add-Linea '| `claves.json` cubierto por `.gitignore` | **NO** | sí |'
}
Add-Linea ('| Vídeos en `salida\` | {0} | — |' -f $med['n_mp4'])
Add-Linea ''
Add-Linea '---'
Add-Linea ''

Add-Linea '## 5. Qué necesito de ti ahora'
Add-Linea ''
if ($pendientes.Count -eq 0) {
    Add-Linea 'No hay preguntas marcadas como `pendiente` en `REVISION_ESTADO.md`.'
    Add-Linea 'Revisa el estado de arriba y propón el siguiente paso.'
} else {
    Add-Linea ('Hay **{0} decisiones pendientes** (§7 del brief):' -f $pendientes.Count)
    Add-Linea ''
    $i = 1
    foreach ($q in $pendientes) { Add-Linea ('{0}. {1}' -f $i, $q); $i++ }
    Add-Linea ''
    Add-Linea 'Responde en el formato de parche de la §0 del brief (ARCHIVO / ANTES / DESPUÉS /'
    Add-Linea 'POR QUÉ / RIESGO / PRUEBA). Si no estás de acuerdo con algún hallazgo, dilo.'
}
Add-Linea ''

$bloque = $sb.ToString()

# ------------------------------------------------------------------ 6. escribir
Escribir-SinBom $ARCHIVO_BLOQUE $bloque

$kb = [math]::Round((Get-Item -Path $ARCHIVO_BLOQUE).Length / 1KB, 1)
$nLineas = @($bloque -split "`n").Count
Write-Host ''
Write-Host ('Bloque generado: .revision\bloque.md  ({0} KB, {1} lineas)' -f $kb, $nLineas) -ForegroundColor Green
if ($hayCambios) {
    Write-Host ('  Codigo cambiado desde el snapshot: {0} modificados, {1} anadidos, {2} borrados' -f $modificados.Count, $anadidos.Count, $borrados.Count) -ForegroundColor Yellow
} else {
    Write-Host '  Codigo identico al snapshot (la revision sigue vigente).' -ForegroundColor DarkGray
}
Write-Host ('  Decisiones pendientes: {0}' -f $pendientes.Count) -ForegroundColor DarkGray

if (-not $SinPortapapeles) {
    try {
        Set-Clipboard -Value $bloque
        Write-Host '  Copiado al portapapeles: pegalo en ChatGPT.' -ForegroundColor Green
    } catch {
        Write-Host '  No pude copiar al portapapeles; abre .revision\bloque.md y copialo a mano.' -ForegroundColor Yellow
    }
}
