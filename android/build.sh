#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK" ]]; then echo 'Define ANDROID_SDK_ROOT.' >&2; exit 2; fi
TOOLS="$SDK/build-tools/35.0.0"
PLATFORM="$SDK/platforms/android-36/android.jar"
for file in "$TOOLS/aapt2" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" "$TOOLS/core-lambda-stubs.jar" "$PLATFORM"; do
  [[ -f "$file" ]] || { echo "Falta herramienta: $file" >&2; exit 2; }
done
command -v javac >/dev/null || { echo 'No se encuentra javac; instala JDK 17 y define JAVA_HOME/PATH.' >&2; exit 2; }
BUILD="$ROOT/build"
mkdir -p "$BUILD/classes" "$BUILD/dex" "$BUILD/generated"
rm -rf "$BUILD/classes" "$BUILD/dex" "$BUILD/generated"
mkdir -p "$BUILD/classes" "$BUILD/dex" "$BUILD/generated"
"$TOOLS/aapt2" compile --dir "$ROOT/res" -o "$BUILD/resources.zip"
"$TOOLS/aapt2" link -o "$BUILD/base.apk" -I "$PLATFORM" --manifest "$ROOT/AndroidManifest.xml" --java "$BUILD/generated" "$BUILD/resources.zip"
find "$ROOT/src" "$BUILD/generated" -name '*.java' -print > "$BUILD/sources.txt"
javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "$PLATFORM:$TOOLS/core-lambda-stubs.jar" -d "$BUILD/classes" @"$BUILD/sources.txt"
jar cf "$BUILD/classes.jar" -C "$BUILD/classes" .
"$TOOLS/d8" --min-api 29 --lib "$PLATFORM" --output "$BUILD/dex" "$BUILD/classes.jar"
cp "$BUILD/base.apk" "$BUILD/unsigned.apk"
python3 - "$BUILD/unsigned.apk" "$BUILD/dex" "$ROOT/assets" <<'PY'
import os, sys, zipfile
apk, dex_dir, assets = sys.argv[1:]
with zipfile.ZipFile(apk, 'a', compression=zipfile.ZIP_DEFLATED) as z:
    for name in sorted(os.listdir(dex_dir)):
        if name.endswith('.dex'): z.write(os.path.join(dex_dir, name), name)
    for base, _, files in os.walk(assets):
        for name in files:
            path = os.path.join(base, name)
            z.write(path, 'assets/' + os.path.relpath(path, assets).replace(os.sep, '/'))
PY
"$TOOLS/zipalign" -f -p 4 "$BUILD/unsigned.apk" "$BUILD/aligned.apk"
SIGNING="$ROOT/.signing"
mkdir -p "$SIGNING"
KS="$SIGNING/shortsreddit.jks"
PASS="$SIGNING/password.txt"
if [[ ! -f "$KS" ]]; then
  if [[ ! -f "$PASS" ]]; then openssl rand -base64 36 > "$PASS"; chmod 600 "$PASS"; fi
  keytool -genkeypair -keystore "$KS" -storepass:file "$PASS" -keypass:file "$PASS" -alias shortsreddit -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Shorts Reddit Personal, OU=Android, O=Shorts Reddit, C=CL' -storetype JKS
fi
DELIVERY="$(dirname "$ROOT")/entrega-android"
mkdir -p "$DELIVERY"
APK="$DELIVERY/ShortsReddit-Android.apk"
"$TOOLS/apksigner" sign --ks "$KS" --ks-key-alias shortsreddit --ks-pass "file:$PASS" --out "$APK" "$BUILD/aligned.apk"
"$TOOLS/apksigner" verify --verbose "$APK"
printf 'APK compilado y firmado: %s\n' "$APK"
