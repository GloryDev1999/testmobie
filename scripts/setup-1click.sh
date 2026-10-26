#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTEMIS_DIR="${REPO_ROOT}/artemis"
PATCH_DIR="${REPO_ROOT}/scripts/patches"
BLENDER_MCP_DIR="${REPO_ROOT}/tools/blender_mcp"
SDK_ROOT="/tmp/android-sdk"
AVD_HOME="/tmp/android-avd"

echo "========================================================"
echo "🚀 [1/6] Cài đặt công cụ hệ thống (uv, ffmpeg, scrcpy, JDK 17, Blender 4.0, Xvfb, gltf-transform)..."
echo "========================================================"
export PATH="${HOME}/.local/bin:${SDK_ROOT}/platform-tools:${SDK_ROOT}/emulator:${PATH}"
mkdir -p "${HOME}/.local/bin"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if ! command -v scrcpy >/dev/null 2>&1 || ! command -v ffmpeg >/dev/null 2>&1 || ! command -v java >/dev/null 2>&1 || ! command -v blender >/dev/null 2>&1 || ! command -v xvfb-run >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ffmpeg scrcpy openjdk-17-jdk-headless unzip wget curl gcc libc6-dev \
    blender xvfb python3-numpy libgl1-mesa-dri libegl1 libgbm1
fi

if ! command -v gltf-transform >/dev/null 2>&1; then
  npm install -g @gltf-transform/cli --no-audit --no-fund
fi

echo "========================================================"
echo "📦 [2/6] Clone & áp dụng bản vá ARTEMIS cho Codespaces..."
echo "========================================================"
if [ ! -d "${ARTEMIS_DIR}/.git" ]; then
  git clone https://github.com/google/artemis.git "${ARTEMIS_DIR}"
fi

cd "${ARTEMIS_DIR}"
if [ -f "${PATCH_DIR}/artemis-codespace.patch" ]; then
  git checkout -- . 2>/dev/null || true
  git apply "${PATCH_DIR}/artemis-codespace.patch"
  echo "✓ Đã áp dụng bản vá artemis-codespace.patch"
fi

echo "========================================================"
echo "🐍 [3/6] Cài đặt Python venv & Build Web UI..."
echo "========================================================"
cd "${ARTEMIS_DIR}"
uv sync

if [ ! -d "${ARTEMIS_DIR}/apps/admin_console/web_dist/browser" ]; then
  cd "${ARTEMIS_DIR}/apps/showcase"
  npm install --no-audit --no-fund
  npm run build
fi

echo "========================================================"
echo "🤖 [4/6] Cài đặt Android SDK & tạo máy ảo Pixel_8_API_34..."
echo "========================================================"
mkdir -p "${SDK_ROOT}/cmdline-tools" "${AVD_HOME}"
if [ ! -x "${SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" ]; then
  CMDLINE_ZIP="/tmp/commandlinetools-linux.zip"
  wget -q -O "${CMDLINE_ZIP}" "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  unzip -q -o "${CMDLINE_ZIP}" -d "${SDK_ROOT}/cmdline-tools"
  rm -rf "${SDK_ROOT}/cmdline-tools/latest"
  mv "${SDK_ROOT}/cmdline-tools/cmdline-tools" "${SDK_ROOT}/cmdline-tools/latest"
  rm -f "${CMDLINE_ZIP}"
fi

export ANDROID_SDK_ROOT="${SDK_ROOT}"
export ANDROID_AVD_HOME="${AVD_HOME}"

yes | "${SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" --sdk_root="${SDK_ROOT}" --licenses >/dev/null 2>&1 || true
"${SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager" --sdk_root="${SDK_ROOT}" \
  "platform-tools" \
  "emulator" \
  "platforms;android-34" \
  "system-images;android-34;google_apis;x86_64"

if [ ! -d "${AVD_HOME}/Pixel_8_API_34.avd" ]; then
  echo "no" | "${SDK_ROOT}/cmdline-tools/latest/bin/avdmanager" create avd \
    --force \
    --name "Pixel_8_API_34" \
    --package "system-images;android-34;google_apis;x86_64" \
    --device "pixel_8"
fi

CONFIG_INI="${AVD_HOME}/Pixel_8_API_34.avd/config.ini"
if [ -f "${CONFIG_INI}" ]; then
  sed -i '/^hw.cpu.ncore/d; /^hw.ramSize/d; /^hw.lcd.width/d; /^hw.lcd.height/d; /^hw.lcd.density/d; /^hw.gpu.enabled/d; /^hw.gpu.mode/d; /^disk.dataPartition.size/d' "${CONFIG_INI}"
  cat << 'EOF' >> "${CONFIG_INI}"
hw.cpu.ncore = 2
hw.ramSize = 2560M
hw.lcd.width = 1080
hw.lcd.height = 2400
hw.lcd.density = 420
hw.gpu.enabled = yes
hw.gpu.mode = swiftshader_indirect
disk.dataPartition.size = 4096M
EOF
fi

echo "========================================================"
echo "🛡️ [5/6] Biên dịch lá chắn SIGTERM (nosigterm.so) & Wrapper..."
echo "========================================================"
gcc -shared -fPIC -O2 "${PATCH_DIR}/nosigterm.c" -o /tmp/nosigterm.so -ldl

if [ -x "${SDK_ROOT}/emulator/emulator" ] && [ ! -x "${SDK_ROOT}/emulator/emulator.real" ]; then
  mv "${SDK_ROOT}/emulator/emulator" "${SDK_ROOT}/emulator/emulator.real"
fi

cat << 'EOF' > "${SDK_ROOT}/emulator/emulator"
#!/bin/bash
export ANDROID_AVD_HOME="/tmp/android-avd"
export ANDROID_SDK_ROOT="/tmp/android-sdk"
if [[ "$*" != *"-avd"* ]] && [[ "$*" != *"@"* ]]; then
  exec /tmp/android-sdk/emulator/emulator.real "$@"
fi
rm -f /tmp/android-avd/Pixel_8_API_34.avd/*.lock
export ANDROID_EMULATOR_WAIT_TIME_BEFORE_KILL=20
export LD_PRELOAD="/tmp/nosigterm.so"
exec /tmp/android-sdk/emulator/emulator.real "$@" \
  -cores 2 \
  -memory 2560 \
  -no-window \
  -no-audio \
  -no-boot-anim \
  -gpu swiftshader_indirect \
  -no-snapshot-save \
  -no-snapshot-load \
  -no-metrics >> /tmp/emulator_avd.log 2>&1
EOF
chmod +x "${SDK_ROOT}/emulator/emulator"

ln -sf "${SDK_ROOT}/platform-tools/adb" "${HOME}/.local/bin/adb"
ln -sf "${SDK_ROOT}/emulator/emulator" "${HOME}/.local/bin/emulator"

echo "========================================================"
echo "⚙️ [6/6] Cấu hình .env và MCP Servers (artemis + blender_3d)..."
echo "========================================================"
ENV_FILE="${ARTEMIS_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  cat << EOF > "${ENV_FILE}"
OPENAI_API_KEY=${OPENAI_API_KEY:-YOUR_API_KEY_HERE}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://api.xkiro.com/v1}
GEMINI_API_KEY=${GEMINI_API_KEY:-}
ARTEMIS_KEEP_DEVICE_AWAKE=false
EOF
  echo "✓ Đã khởi tạo ${ENV_FILE}"
fi

for MCP_DIR in "${HOME}/.gemini/config" "${HOME}/.gemini/jetski"; do
  mkdir -p "${MCP_DIR}"
  cat << EOF > "${MCP_DIR}/mcp_config.json"
{
  "mcpServers": {
    "artemis": {
      "command": "${ARTEMIS_DIR}/.venv/bin/python",
      "args": ["-m", "artemis.mcp_server"],
      "cwd": "${ARTEMIS_DIR}",
      "env": {
        "PATH": "${HOME}/.local/bin:/tmp/android-sdk/platform-tools:/tmp/android-sdk/emulator:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "ANDROID_SDK_ROOT": "/tmp/android-sdk",
        "ANDROID_AVD_HOME": "/tmp/android-avd",
        "ARTEMIS_KEEP_DEVICE_AWAKE": "false"
      }
    },
    "blender_3d": {
      "command": "${ARTEMIS_DIR}/.venv/bin/python",
      "args": ["${BLENDER_MCP_DIR}/server.py"],
      "cwd": "${REPO_ROOT}",
      "env": {
        "PATH": "${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
      }
    }
  }
}
EOF
done

echo "✅ Hoàn tất cài đặt 1-Click (ARTEMIS + Android Emulator + Blender 3D MCP)!"
