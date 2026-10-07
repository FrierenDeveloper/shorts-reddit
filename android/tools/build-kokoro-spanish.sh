#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK" ]]; then echo 'Define ANDROID_SDK_ROOT para apksigner.' >&2; exit 2; fi
TOOLS="$SDK/build-tools/35.0.0"
BUILD="$ROOT/build"
ORIGINAL="$BUILD/kokoro-multilang-v1_0.apk"
APKTOOL="$BUILD/apktool.jar"
DECODED="$BUILD/kokoro-decoded-v1_0"
URL='https://huggingface.co/csukuangfj2/sherpa-onnx-apk/resolve/main/tts-engine-new/1.13.8/sherpa-onnx-1.13.8-arm64-v8a-eng-tts-engine-kokoro-multi-lang-v1_0.apk'
mkdir -p "$BUILD/apktool-framework"
if [[ ! -s "$ORIGINAL" ]]; then curl -fL --retry 3 "$URL" -o "$ORIGINAL"; fi
if [[ ! -s "$APKTOOL" ]]; then curl -fL --retry 3 'https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar' -o "$APKTOOL"; fi
rm -rf "$DECODED"
java -jar "$APKTOOL" d -q -f --frame-path "$BUILD/apktool-framework" "$ORIGINAL" -o "$DECODED"
python3 - "$DECODED" <<'PY'
from pathlib import Path
import re, sys
root=Path(sys.argv[1])
old='com.k2fsa.sherpa.onnx.tts.engine'; new='com.shortsreddit.voice.kokoro'
p=root/'AndroidManifest.xml'; s=p.read_text()
assert f'package="{old}"' in s
s=s.replace(f'package="{old}"',f'package="{new}"',1)
s=s.replace(old+'.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION',new+'.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION')
s=s.replace('android:authorities="'+old+'.','android:authorities="'+new+'.')
p.write_text(s)
p=root/'res/values/strings.xml'; s=p.read_text()
s,n=re.subn(r'(<string name="app_name">).*?(</string>)',r'\1Kokoro · Español\2',s,count=1)
assert n == 1
p.write_text(s)
p=root/'smali_classes2/com/k2fsa/sherpa/onnx/tts/engine/TtsEngine.smali'; s=p.read_text()
oldblock='    const-string v0, "eng"\n\n    sput-object v0, Lcom/k2fsa/sherpa/onnx/tts/engine/TtsEngine;->lang:Ljava/lang/String;\n\n    const-string v0, "zho"\n\n    sput-object v0, Lcom/k2fsa/sherpa/onnx/tts/engine/TtsEngine;->lang2:Ljava/lang/String;'
newblock='    const-string v0, "spa"\n\n    sput-object v0, Lcom/k2fsa/sherpa/onnx/tts/engine/TtsEngine;->lang:Ljava/lang/String;\n\n    const-string v0, "eng"\n\n    sput-object v0, Lcom/k2fsa/sherpa/onnx/tts/engine/TtsEngine;->lang2:Ljava/lang/String;'
assert oldblock in s; p.write_text(s.replace(oldblock,newblock))
p=root/'smali/PreferenceHelper.smali'; s=p.read_text(); start=s.index('.method public final getSid()I'); end=s.index('.end method',start); block=s[start:end]; assert 'const/4 v2, 0x0' in block; s=s[:start]+block.replace('const/4 v2, 0x0','const/16 v2, 0x1c',1)+s[end:]; p.write_text(s)
PY
java -jar "$APKTOOL" b -q --frame-path "$BUILD/apktool-framework" "$DECODED" -o "$BUILD/kokoro-patched-unsigned.apk"
"$TOOLS/zipalign" -f -p 4 "$BUILD/kokoro-patched-unsigned.apk" "$BUILD/kokoro-aligned.apk"
"$TOOLS/apksigner" sign --ks "$ROOT/.signing/shortsreddit.jks" --ks-key-alias shortsreddit --ks-pass "file:$ROOT/.signing/password.txt" --out "$(dirname "$ROOT")/entrega-android/ShortsReddit-Kokoro-Espanol.apk" "$BUILD/kokoro-aligned.apk"
"$TOOLS/apksigner" verify --verbose "$(dirname "$ROOT")/entrega-android/ShortsReddit-Kokoro-Espanol.apk"
