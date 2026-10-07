param([string]$AndroidSdk="$env:USERPROFILE\.bubblewrap\android_sdk",[string]$JavaHome="$env:USERPROFILE\.bubblewrap\jdk\jdk-17.0.11+9")
$ErrorActionPreference='Stop'
if ($env:ANDROID_HOME) { $AndroidSdk=$env:ANDROID_HOME }
if ($env:JAVA_HOME) { $JavaHome=$env:JAVA_HOME }
$env:JAVA_HOME=$JavaHome
$env:PATH=(Join-Path $JavaHome 'bin')+';'+$env:PATH
$projectRoot=Split-Path $PSScriptRoot -Parent
$buildDir=Join-Path $projectRoot 'build\checks'
$toolsDir=Join-Path $AndroidSdk 'build-tools\35.0.0'
$platform=Join-Path $AndroidSdk 'platforms\android-36\android.jar'
New-Item -ItemType Directory -Force -Path $buildDir,(Join-Path $buildDir 'classes'),(Join-Path $buildDir 'dex') | Out-Null
function Checked([string]$cmd,[string[]]$arguments) { & $cmd @arguments; if($LASTEXITCODE -ne 0){throw "Falló $cmd ($LASTEXITCODE)"} }
Checked (Join-Path $toolsDir 'aapt2.exe') @('link','-I',$platform,'--manifest',(Join-Path $PSScriptRoot 'device-test\AndroidManifest.xml'),'-o',(Join-Path $buildDir 'base.apk'))
$testSources=@(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'device-test') -Filter '*.java' | ForEach-Object {$_.FullName})
Checked (Join-Path $JavaHome 'bin\javac.exe') (@('-encoding','UTF-8','-source','8','-target','8','-bootclasspath',($platform+';'+(Join-Path $toolsDir 'core-lambda-stubs.jar')),'-classpath',(Join-Path $projectRoot 'build\classes.jar'),'-d',(Join-Path $buildDir 'classes'))+$testSources)
Checked (Join-Path $JavaHome 'bin\jar.exe') @('cf',(Join-Path $buildDir 'checks.jar'),'-C',(Join-Path $buildDir 'classes'),'.')
Checked (Join-Path $toolsDir 'd8.bat') @('--min-api','29','--lib',$platform,'--classpath',(Join-Path $projectRoot 'build\classes.jar'),'--output',(Join-Path $buildDir 'dex'),(Join-Path $buildDir 'checks.jar'))
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$zip=[IO.Compression.ZipFile]::Open((Join-Path $buildDir 'base.apk'),[IO.Compression.ZipArchiveMode]::Update)
try{[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,(Join-Path $buildDir 'dex\classes.dex'),'classes.dex')|Out-Null}finally{$zip.Dispose()}
Checked (Join-Path $toolsDir 'zipalign.exe') @('-f','4',(Join-Path $buildDir 'base.apk'),(Join-Path $buildDir 'aligned.apk'))
Checked (Join-Path $toolsDir 'apksigner.bat') @('sign','--ks',(Join-Path $projectRoot '.signing\shortsreddit.jks'),'--ks-pass',('file:'+(Join-Path $projectRoot '.signing\password.txt')),'--out',(Join-Path $buildDir 'checks.apk'),(Join-Path $buildDir 'aligned.apk'))
