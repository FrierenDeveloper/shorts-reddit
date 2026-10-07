param([switch]$IncluirTransferencia)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$projectRoot=Split-Path $PSScriptRoot -Parent
$delivery=Join-Path $projectRoot 'entrega-android'
New-Item -ItemType Directory -Force -Path $delivery | Out-Null
$source=Join-Path $delivery 'Codigo-Android.zip'
if(Test-Path -LiteralPath $source){Remove-Item -LiteralPath $source}
$zip=[IO.Compression.ZipFile]::Open($source,[IO.Compression.ZipArchiveMode]::Create)
try {foreach($file in Get-ChildItem -LiteralPath $PSScriptRoot -Recurse -File){$relative=$file.FullName.Substring($PSScriptRoot.Length+1).Replace('\','/');if($relative.StartsWith('build/') -or $relative.StartsWith('.signing/')){continue};[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$file.FullName,('android/'+$relative),[IO.Compression.CompressionLevel]::Optimal)|Out-Null}} finally {$zip.Dispose()}
$names=@('ShortsReddit-Android.apk','ShortsReddit-Kokoro-Espanol.apk','Codigo-Android.zip','LEEME_ANDROID.md','VALIDACION_ANDROID.md','VOCES_ANDROID.md','Piper-Daniela-Argentina.apk','Piper-Claude-Mexico.apk','INTERPRETACION_VOZ.md','TERCEROS.md','ejemplo-verificado.mp4','voces-verificadas.m4a','pantalla-android.png')
foreach($name in @('LEEME_ANDROID.md','VALIDACION_ANDROID.md','VOCES_ANDROID.md','INTERPRETACION_VOZ.md','TERCEROS.md')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $delivery $name) -Force}
if($IncluirTransferencia){$names+='Proyecto-para-importar.zip'}
$manifest=foreach($name in $names){$path=Join-Path $delivery $name;if(Test-Path -LiteralPath $path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()+'  '+$name}}
[IO.File]::WriteAllLines((Join-Path $delivery 'SHA256.txt'),$manifest,[Text.UTF8Encoding]::new($false))
$names+='SHA256.txt'
$complete=Join-Path $delivery 'ShortsReddit-Android-Completo.zip'
if(Test-Path -LiteralPath $complete){Remove-Item -LiteralPath $complete}
$zip=[IO.Compression.ZipFile]::Open($complete,[IO.Compression.ZipArchiveMode]::Create)
try{foreach($name in $names){$path=Join-Path $delivery $name;if(Test-Path -LiteralPath $path){[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$path,$name,[IO.Compression.CompressionLevel]::NoCompression)|Out-Null}}}finally{$zip.Dispose()}
Write-Output "Paquete sin biblioteca antigua: $complete"
