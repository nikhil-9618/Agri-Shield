#!/usr/bin/env bash
# User-space (no root) install of JDK 17 + Flutter SDK + Android SDK.
# Everything lands in $HOME/toolchain so it never bloats the project checkpoint.
set -euo pipefail

TC="$HOME/toolchain"
mkdir -p "$TC"
cd "$TC"
echo "== toolchain install started $(date -u) =="

# ---------------------------------------------------------------- JDK 17
if [ ! -x "$TC/jdk/bin/java" ]; then
  echo "[1/4] Downloading Temurin JDK 17..."
  curl -fL --retry 3 -o jdk17.tar.gz \
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
  mkdir -p jdk
  tar xzf jdk17.tar.gz -C jdk --strip-components=1
  rm -f jdk17.tar.gz
fi
export JAVA_HOME="$TC/jdk"
export PATH="$JAVA_HOME/bin:$PATH"
java -version

# --------------------------------------------------------------- Flutter
if [ ! -x "$TC/flutter/bin/flutter" ]; then
  echo "[2/4] Resolving latest stable Flutter release..."
  ARCHIVE=$(curl -fsSL https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); h=d['current_release']['stable']; r=[x for x in d['releases'] if x['hash']==h][0]; print(r['archive'])")
  echo "     archive: $ARCHIVE"
  curl -fL --retry 3 -o flutter.tar.xz "https://storage.googleapis.com/flutter_infra_release/releases/$ARCHIVE"
  tar xf flutter.tar.xz
  rm -f flutter.tar.xz
fi
export PATH="$TC/flutter/bin:$PATH"
git config --global --add safe.directory "$TC/flutter" 2>/dev/null || true
flutter --version

# ----------------------------------------------------------- Android SDK
export ANDROID_SDK_ROOT="$TC/android-sdk"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
if [ ! -x "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]; then
  echo "[3/4] Downloading Android command-line tools..."
  curl -fL --retry 3 -o cmdline-tools.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  rm -rf cmdline-tools-tmp && mkdir cmdline-tools-tmp
  unzip -q cmdline-tools.zip -d cmdline-tools-tmp
  rm -rf "$ANDROID_SDK_ROOT/cmdline-tools/latest"
  mv cmdline-tools-tmp/cmdline-tools "$ANDROID_SDK_ROOT/cmdline-tools/latest"
  rm -rf cmdline-tools-tmp cmdline-tools.zip
fi
SDKM="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
export PATH="$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"

echo "[4/4] Installing SDK packages (licenses auto-accepted)..."
yes | "$SDKM" --sdk_root="$ANDROID_SDK_ROOT" --licenses >/dev/null 2>&1 || true
"$SDKM" --sdk_root="$ANDROID_SDK_ROOT" "platform-tools" "platforms;android-35" "build-tools;35.0.0" || \
  "$SDKM" --sdk_root="$ANDROID_SDK_ROOT" "platform-tools" "platforms;android-34" "build-tools;34.0.0"

flutter config --android-sdk "$ANDROID_SDK_ROOT" --no-analytics >/dev/null 2>&1 || true
flutter config --jdk-dir "$JAVA_HOME" >/dev/null 2>&1 || true

echo "== toolchain install finished $(date -u) =="
flutter doctor -v || true
