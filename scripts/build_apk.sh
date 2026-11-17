#!/usr/bin/env bash
# Build the signed release APK.
#
# Prerequisites: JDK 17, Flutter stable, Android SDK platform 36.
# `scripts/setup_android_toolchain.sh` installs all three into ~/toolchain
# without root; this script uses that location by default.
#
#   ./scripts/build_apk.sh
#   AGRI_API_BASE_URL=http://192.168.1.20:8000 ./scripts/build_apk.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-$HOME/toolchain/jdk}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/toolchain/android-sdk}"
export PATH="$HOME/toolchain/flutter/bin:$JAVA_HOME/bin:$PATH"

cd "$REPO_ROOT/mobile"

if [ ! -f android/key.properties ]; then
  echo "no android/key.properties: generating a local release keystore"
  PASS="$(openssl rand -hex 16)"
  "$JAVA_HOME/bin/keytool" -genkeypair -v \
    -keystore android/app/agrishield-release.jks -alias agrishield \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$PASS" -keypass "$PASS" \
    -dname "CN=AgriShield, OU=Mobile, O=AgriShield, L=Hyderabad, ST=Telangana, C=IN" \
    >/dev/null
  printf 'storePassword=%s\nkeyPassword=%s\nkeyAlias=agrishield\nstoreFile=agrishield-release.jks\n' \
    "$PASS" "$PASS" > android/key.properties
  echo "keep android/app/agrishield-release.jks and android/key.properties safe:"
  echo "you need the same key to ship updates to an installed app."
fi

flutter pub get
flutter analyze
flutter build apk --release \
  --build-name 1.2.0 --build-number 6 \
  --dart-define=AGRI_API_BASE_URL="${AGRI_API_BASE_URL:-http://10.0.2.2:8000}"

mkdir -p "$REPO_ROOT/artifacts"
cp build/app/outputs/flutter-apk/app-release.apk \
  "$REPO_ROOT/artifacts/agrishield-1.2.0-universal.apk"
echo "APK: artifacts/agrishield-1.2.0-universal.apk"
