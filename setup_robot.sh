#!/bin/bash
# ============================================================
# setup_robot.sh
# Cài đặt môi trường cho Robot Streaming (Pi 3B+ / Pi 4 / Pi 5)
# Video + Âm thanh 2 chiều: Python → MediaMTX → WebRTC Browser
# ============================================================
set -e

MEDIAMTX_VERSION="v1.9.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Phát hiện kiến trúc CPU ──────────────────────────────────
ARCH=$(uname -m)
case "${ARCH}" in
  aarch64) MTX_ARCH="linux_arm64v8" ;;
  armv7l)  MTX_ARCH="linux_armv7"   ;;
  armv6l)  MTX_ARCH="linux_armv6"   ;;
  x86_64)  MTX_ARCH="linux_amd64"   ;;
  *)
    echo "[!] Kiến trúc không hỗ trợ: ${ARCH}"
    exit 1 ;;
esac
echo "[*] Kiến trúc: ${ARCH} → MediaMTX binary: ${MTX_ARCH}"

# ── Cập nhật hệ thống & cài gói ─────────────────────────────
echo "[*] Cài đặt ffmpeg, python3-opencv, alsa-utils..."
sudo apt-get update -qq
sudo apt-get install -y \
  ffmpeg \
  python3-opencv \
  python3-pip \
  python3-requests \
  alsa-utils \
  v4l-utils

# ── Cài Python packages ──────────────────────────────────────
echo "[*] Cài Python packages..."
pip3 install --break-system-packages requests 2>/dev/null \
  || pip3 install requests

# ── Tải MediaMTX ─────────────────────────────────────────────
MTX_TARBALL="mediamtx_${MEDIAMTX_VERSION}_${MTX_ARCH}.tar.gz"
MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/${MTX_TARBALL}"
MTX_DIR="${SCRIPT_DIR}/mediamtx"

if [ -f "${MTX_DIR}/mediamtx" ]; then
  echo "[*] MediaMTX đã tồn tại, bỏ qua tải xuống."
else
  echo "[*] Tải MediaMTX ${MEDIAMTX_VERSION} (${MTX_ARCH})..."
  mkdir -p "${MTX_DIR}"
  wget -q --show-progress "${MTX_URL}" -O "/tmp/${MTX_TARBALL}"
  tar -xzf "/tmp/${MTX_TARBALL}" -C "${MTX_DIR}"
  rm -f "/tmp/${MTX_TARBALL}"
  echo "[✓] MediaMTX đã giải nén vào ${MTX_DIR}/"
fi

# ── Copy file cấu hình ──────────────────────────────────────
if [ ! -f "${MTX_DIR}/mediamtx.yml" ]; then
  cp "${SCRIPT_DIR}/mediamtx.yml" "${MTX_DIR}/mediamtx.yml"
  echo "[✓] Đã copy mediamtx.yml vào ${MTX_DIR}/"
fi

chmod +x "${MTX_DIR}/mediamtx"

# ── Kiểm tra Camera ─────────────────────────────────────────
echo "[*] Kiểm tra thiết bị camera..."
v4l2-ctl --list-devices 2>/dev/null || echo "[!] v4l2-ctl không tìm thấy thiết bị."

# ── Kiểm tra ALSA / Mic ──────────────────────────────────────
echo "[*] Thiết bị ghi âm ALSA:"
arecord -l 2>/dev/null || echo "[!] Không tìm thấy thiết bị ghi âm."

echo ""
echo "======================================================"
echo "[✓] Cài đặt hoàn tất!"
echo ""
echo "Thứ tự chạy:"
echo "  1.  cd $(dirname "$0")"
echo "  2.  ./start.sh"
echo "  3.  Mở trình duyệt: http://$(hostname -I | awk '{print $1}'):8889/robot"
echo "======================================================"
