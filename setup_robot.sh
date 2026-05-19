#!/usr/bin/env bash
# =============================================================================
# setup_robot.sh ? One-shot setup for video-stream-robot
# Works on: Raspberry Pi 3B+/4/5 (arm64, armv7) and Linux x86_64
# =============================================================================
set -euo pipefail

MEDIAMTX_VERSION="v1.9.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# app.py expects mediamtx at ../rc-car/mediamtx relative to the repo
RC_CAR_DIR="$(dirname "${SCRIPT_DIR}")/rc-car"
MTX_BIN="${RC_CAR_DIR}/mediamtx"
VENV_DIR="${SCRIPT_DIR}/.venv"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[?]${NC} $*"; }
info() { echo -e "${YELLOW}[*]${NC} $*"; }

# ?? Detect architecture ???????????????????????????????????????
ARCH=$(uname -m)
case "${ARCH}" in
  aarch64) MTX_ARCH="linux_arm64v8" ;;
  armv7l)  MTX_ARCH="linux_armv7"   ;;
  armv6l)  MTX_ARCH="linux_armv6"   ;;
  x86_64)  MTX_ARCH="linux_amd64"   ;;
  *)
    echo "[!] Unsupported architecture: ${ARCH}"; exit 1 ;;
esac
info "Architecture: ${ARCH} ? MediaMTX binary: ${MTX_ARCH}"

# ?? System packages ????????????????????????????????????????????
info "Installing system packages (ffmpeg, python3-venv, openssl, v4l-utils)..."
sudo apt-get update -qq
sudo apt-get install -y \
  ffmpeg \
  python3-pip \
  swig \
  liblgpio-dev \
  python3-venv \
  python3-picamera2 \
  alsa-utils \
  v4l-utils \
  openssl \
  curl
ok "System packages installed."

# ?? Python venv ????????????????????????????????????????????????
if [ ! -f "${VENV_DIR}/bin/python" ]; then
  info "Creating Python venv at ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
fi
info "Installing Python packages (flask, gunicorn)..."
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install rpi-lgpio -q
"${VENV_DIR}/bin/pip" install flask gunicorn -q
"${VENV_DIR}/bin/pip" install pyserial pynmea2 opencv-python-headless pytest pytest-mock -q
ok "Python venv ready at ${VENV_DIR}"

# ?? Download MediaMTX ??????????????????????????????????????????
if [ -f "${MTX_BIN}" ]; then
  ok "MediaMTX already at ${MTX_BIN}, skipping download."
else
  MTX_TARBALL="mediamtx_${MEDIAMTX_VERSION}_${MTX_ARCH}.tar.gz"
  MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/${MTX_TARBALL}"
  info "Downloading MediaMTX ${MEDIAMTX_VERSION} (${MTX_ARCH})..."
  mkdir -p "${RC_CAR_DIR}"
  wget -q --show-progress "${MTX_URL}" -O "/tmp/${MTX_TARBALL}"
  tar -xzf "/tmp/${MTX_TARBALL}" -C "${RC_CAR_DIR}" mediamtx
  rm -f "/tmp/${MTX_TARBALL}"
  chmod +x "${MTX_BIN}"
  ok "MediaMTX extracted to ${MTX_BIN}"
fi

# ?? Tailscale (optional) ???????????????????????????????????????
if command -v tailscale &>/dev/null; then
  ok "Tailscale already installed ($(tailscale version 2>/dev/null | head -1))."
else
  read -r -p "[?] Install Tailscale for remote/4G access? [y/N] " _ts
  if [[ "${_ts,,}" == "y" ]]; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    ok "Tailscale installed. Run 'sudo tailscale up' to authenticate."
  fi
fi

# ?? Systemd service ????????????????????????????????????????????
SERVICE_SRC="${SCRIPT_DIR}/robot-stream.service"
SERVICE_DST="/etc/systemd/system/robot-stream.service"
read -r -p "[?] Install systemd autostart service? [y/N] " _svc
if [[ "${_svc,,}" == "y" ]]; then
  sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
  sudo systemctl daemon-reload
  sudo systemctl enable robot-stream
  ok "Service installed and enabled (starts on next boot)."
  echo "    Start now : sudo systemctl start robot-stream"
  echo "    View logs : journalctl -u robot-stream -f"
fi

# ?? Camera / audio sanity check ????????????????????????????????
echo ""
info "Camera devices:"
v4l2-ctl --list-devices 2>/dev/null || echo "  (none found ? check camera cable)"
info "Audio capture devices:"
arecord -l 2>/dev/null || echo "  (none found)"

# ?? Done ????????????????????????????????????????????????????????
PI_IP=$(hostname -I | awk '{print $1}')
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "N/A")
echo ""
echo "======================================================"
ok "Setup complete!"
echo ""
echo "  Start manually:"
echo "    cd ${SCRIPT_DIR}"
echo "    nohup .venv/bin/python app.py > server.log 2>&1 &"
echo ""
echo "  Then open in browser (accept the self-signed cert):"
echo "    https://${PI_IP}:5000            (LAN)"
[ "${TAILSCALE_IP}" != "N/A" ] && \
echo "    https://${TAILSCALE_IP}:5000      (Tailscale/4G)"
echo "======================================================"
