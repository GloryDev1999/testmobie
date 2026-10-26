#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTEMIS_DIR="${REPO_ROOT}/artemis"
SDK_ROOT="/tmp/android-sdk"
AVD_HOME="/tmp/android-avd"

export PATH="${HOME}/.local/bin:${SDK_ROOT}/platform-tools:${SDK_ROOT}/emulator:${PATH}"
export ANDROID_SDK_ROOT="${SDK_ROOT}"
export ANDROID_AVD_HOME="${AVD_HOME}"
export ARTEMIS_KEEP_DEVICE_AWAKE="false"

# Nếu /tmp bị xóa sau khi Codespace reboot, tự động chạy lại setup-1click.sh
if [ ! -x "${SDK_ROOT}/emulator/emulator.real" ] || [ ! -f "/tmp/nosigterm.so" ] || [ ! -d "${ARTEMIS_DIR}/.venv" ]; then
  echo "🔄 Phát hiện môi trường /tmp mới, đang tự động khôi phục SDK & AVD..."
  bash "${REPO_ROOT}/scripts/setup-1click.sh"
fi

# 1. Khởi động ADB server
adb start-server >/dev/null 2>&1 || true

# 2. Khởi động Artemis Web Daemon trên cổng 8000 (nếu chưa chạy)
mkdir -p "${HOME}/.gemini/jetski/logs"
if ! pgrep -f "apps.admin_console.server" >/dev/null 2>&1; then
  echo "🌐 Đang khởi động Artemis Web Daemon tại http://127.0.0.1:8000 ..."
  cd "${ARTEMIS_DIR}"
  nohup uv run python -m apps.admin_console.server > "${HOME}/.gemini/jetski/logs/daemon-8000.log" 2>&1 &
fi

# 3. Khởi động máy ảo Pixel_8_API_34 (nếu chưa chạy)
if ! adb devices | grep -q "emulator-5554"; then
  echo "📱 Đang khởi động máy ảo Pixel_8_API_34 (emulator-5554)..."
  nohup "${SDK_ROOT}/emulator/emulator" -avd Pixel_8_API_34 >/dev/null 2>&1 &
fi

echo "⏳ Đang đợi máy ảo emulator-5554 boot hoàn tất..."
for i in $(seq 1 90); do
  BOOT_DONE="$(adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [ "${BOOT_DONE}" = "1" ]; then
    break
  fi
  sleep 2
done

# 4. Mở khóa màn hình & gắn Accessibility Helper
adb -s emulator-5554 shell wm dismiss-keyguard >/dev/null 2>&1 || true
cd "${ARTEMIS_DIR}"
uv run python -c "
from artemis.runtime.helper_manager import helper_manager
print('✓ Accessibility Helper:', helper_manager.attach('emulator-5554', provision=True))
"

echo "🎉 Hệ thống đã sẵn sàng 100% (Port 8000 + emulator-5554)!"
