param([string]$JavaHome="$env:USERPROFILE\.bubblewrap\jdk\jdk-17.0.11+9",[string]$AndroidSdk="$env:USERPROFILE\.bubblewrap\android_sdk")
# Repackage the official Claude engine with a distinct application id so Daniela can coexist.
# Executable DEX, native libraries and voice model remain unchanged. Only manifest identity,
# provider authorities, permission names and the launcher label are changed.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$work=Join-Path $root 'build'
$java=Join-Path $JavaHome 'bin/java.exe'
$apktool=Join-Path $work 'apktool.jar'
$input=Join-Path $work 'es_MX-claude-high.apk'
if(!(Test-Path $input)){Invoke-WebRequest 'https://huggingface.co/csukuangfj2/sherpa-onnx-apk/resolve/main/tts-engine-new/1.13.8/sherpa-onnx-1.13.8-arm64-v8a-spa-tts-engine-vits-piper-es_MX-claude-high.apk' -OutFile $input}
if(!(Test-Path $apktool)){Invoke-WebRequest 'https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar' -OutFile $apktool}
$decoded=Join-Path $work 'claude-coexist'
& $java -jar $apktool d -f -s $input -o $decoded
if($LASTEXITCODE -ne 0){throw 'No se pudo extraer el motor'}
$manifest=Join-Path $decoded 'AndroidManifest.xml'
$text=[IO.File]::ReadAllText($manifest)
$text=$text.Replace('package="com.k2fsa.sherpa.onnx.tts.engine"','package="com.shortsreddit.voice.claude"')
$text=$text.Replace('com.k2fsa.sherpa.onnx.tts.engine.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION','com.shortsreddit.voice.claude.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION')
$text=$text.Replace('android:authorities="com.k2fsa.sherpa.onnx.tts.engine.','android:authorities="com.shortsreddit.voice.claude.')
[IO.File]::WriteAllText($manifest,$text,[Text.UTF8Encoding]::new($false))
$strings=Join-Path $decoded 'res/values/strings.xml'
$text=[IO.File]::ReadAllText($strings)
$text=[regex]::Replace($text,'(<string name="app_name">).*?(</string>)','${1}Piper Claude - Mexico${2}')
[IO.File]::WriteAllText($strings,$text,[Text.UTF8Encoding]::new($false))
$unsigned=Join-Path $work 'claude-unsigned.apk'
$aligned=Join-Path $work 'claude-aligned.apk'
& $java -jar $apktool b $decoded -o $unsigned
if($LASTEXITCODE -ne 0){throw 'No se pudo compilar el motor'}
$env:JAVA_HOME=$JavaHome
$env:PATH=(Join-Path $JavaHome 'bin')+';'+$env:PATH
$buildTools=Join-Path $AndroidSdk 'build-tools/35.0.0'
& (Join-Path $buildTools 'zipalign.exe') -f -p 4 $unsigned $aligned
if($LASTEXITCODE -ne 0){throw 'Falló zipalign'}
& (Join-Path $buildTools 'apksigner.bat') sign --ks (Join-Path $root '.signing/shortsreddit.jks') --ks-pass ('file:'+(Join-Path $root '.signing/password.txt')) --out (Join-Path (Split-Path $root -Parent) 'entrega-android/Piper-Claude-Mexico.apk') $aligned
if($LASTEXITCODE -ne 0){throw 'Falló la firma'}
