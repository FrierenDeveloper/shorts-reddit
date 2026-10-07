param(
    [string]$AndroidSdk = "$env:USERPROFILE\.bubblewrap\android_sdk",
    [string]$JavaHome = "$env:USERPROFILE\.bubblewrap\jdk\jdk-17.0.11+9"
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if ($env:ANDROID_HOME) { $AndroidSdk = $env:ANDROID_HOME }
if ($env:JAVA_HOME) { $JavaHome = $env:JAVA_HOME }
$sdkJar = Join-Path $AndroidSdk 'platforms\android-36\android.jar'
if (!(Test-Path -LiteralPath $sdkJar)) { throw 'Instala la plataforma android-36 del SDK, o indica -AndroidSdk.' }
$toolsDir = Join-Path $AndroidSdk 'build-tools\35.0.0'
if (!(Test-Path -LiteralPath $toolsDir)) { $toolsDir = (Get-ChildItem -LiteralPath (Join-Path $AndroidSdk 'build-tools') -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName }
if (!(Test-Path -LiteralPath (Join-Path $JavaHome 'bin\javac.exe'))) { throw 'Se necesita JDK 17. Indica -JavaHome.' }
$env:JAVA_HOME = $JavaHome
$env:PATH = (Join-Path $JavaHome 'bin') + ';' + $env:PATH
$buildDir = Join-Path $projectRoot 'build'
New-Item -ItemType Directory -Force -Path $buildDir,(Join-Path $buildDir 'classes'),(Join-Path $buildDir 'dex'),(Join-Path $buildDir 'generated') | Out-Null
function Invoke-Checked([string]$tool,[string[]]$arguments) { & $tool @arguments; if ($LASTEXITCODE -ne 0) { throw "Error $LASTEXITCODE en $tool" } }
Invoke-Checked (Join-Path $toolsDir 'aapt2.exe') @('compile','--dir',(Join-Path $projectRoot 'res'),'-o',(Join-Path $buildDir 'resources.zip'))
Invoke-Checked (Join-Path $toolsDir 'aapt2.exe') @('link','-o',(Join-Path $buildDir 'base.apk'),'-I',$sdkJar,'--manifest',(Join-Path $projectRoot 'AndroidManifest.xml'),'--java',(Join-Path $buildDir 'generated'),(Join-Path $buildDir 'resources.zip'))
$sources = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'src'),(Join-Path $buildDir 'generated') -Recurse -Filter '*.java' | ForEach-Object { '"' + $_.FullName.Replace('\','/') + '"' })
[IO.File]::WriteAllLines((Join-Path $buildDir 'sources.txt'),$sources,[Text.UTF8Encoding]::new($false))
Invoke-Checked (Join-Path $JavaHome 'bin\javac.exe') @('-encoding','UTF-8','-source','8','-target','8','-bootclasspath',($sdkJar+';'+(Join-Path $toolsDir 'core-lambda-stubs.jar')),'-d',(Join-Path $buildDir 'classes'),('@'+(Join-Path $buildDir 'sources.txt')))
Invoke-Checked (Join-Path $JavaHome 'bin\jar.exe') @('cf',(Join-Path $buildDir 'classes.jar'),'-C',(Join-Path $buildDir 'classes'),'.')
Invoke-Checked (Join-Path $toolsDir 'd8.bat') @('--min-api','29','--lib',$sdkJar,'--output',(Join-Path $buildDir 'dex'),(Join-Path $buildDir 'classes.jar'))
$unsigned = Join-Path $buildDir 'unsigned.apk'
Copy-Item -LiteralPath (Join-Path $buildDir 'base.apk') -Destination $unsigned -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$zip = [IO.Compression.ZipFile]::Open($unsigned,[IO.Compression.ZipArchiveMode]::Update)
try {
    foreach ($dex in Get-ChildItem -LiteralPath (Join-Path $buildDir 'dex') -Filter '*.dex') { [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$dex.FullName,$dex.Name,[IO.Compression.CompressionLevel]::Optimal) | Out-Null }
    $assetsRoot=Join-Path $projectRoot 'assets'
    foreach($asset in Get-ChildItem -LiteralPath $assetsRoot -Recurse -File){$entry='assets/'+$asset.FullName.Substring($assetsRoot.Length+1).Replace('\','/');[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$asset.FullName,$entry,[IO.Compression.CompressionLevel]::Optimal)|Out-Null}
} finally { $zip.Dispose() }
$aligned = Join-Path $buildDir 'aligned.apk'
Invoke-Checked (Join-Path $toolsDir 'zipalign.exe') @('-f','-p','4',$unsigned,$aligned)
$signing = Join-Path $projectRoot '.signing'
New-Item -ItemType Directory -Force -Path $signing | Out-Null
$keystore = Join-Path $signing 'shortsreddit.jks'
$password = Join-Path $signing 'password.txt'
if (!(Test-Path -LiteralPath $keystore)) {
    $random = [byte[]]::new(32); [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($random)
    [IO.File]::WriteAllText($password,[Convert]::ToBase64String($random),[Text.UTF8Encoding]::new($false))
    Invoke-Checked (Join-Path $JavaHome 'bin\keytool.exe') @('-genkeypair','-keystore',$keystore,'-storepass:file',$password,'-keypass:file',$password,'-alias','shortsreddit','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Shorts Reddit Personal, OU=Android, O=Shorts Reddit, C=CL','-storetype','JKS')
}
$delivery = Join-Path (Split-Path $projectRoot -Parent) 'entrega-android'
New-Item -ItemType Directory -Force -Path $delivery | Out-Null
$apk = Join-Path $delivery 'ShortsReddit-Android.apk'
Invoke-Checked (Join-Path $toolsDir 'apksigner.bat') @('sign','--ks',$keystore,'--ks-key-alias','shortsreddit','--ks-pass',('file:'+$password),'--out',$apk,$aligned)
Invoke-Checked (Join-Path $toolsDir 'apksigner.bat') @('verify','--verbose',$apk)
Write-Output "APK compilado y firmado: $apk"
