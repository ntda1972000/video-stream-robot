#!/bin/bash
# ============================================================
# start.sh — Khởi động MediaMTX + Python Publisher cùng lúc
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MTX_BIN="${SCRIPT_DIR}/mediamtx/mediamtx"
MTX_CFG="${SCRIPT_DIR}/mediamtx.yml"

# ── Kiểm tra MediaMTX ────────────────────────────────────────
if [ ! -f "${MTX_BIN}" ]; then
  echo "[!] MediaMTX chưa được cài. Chạy ./setup_robot.sh trước."
  exit 1
fi

# ── Dọn dẹp khi tắt ─────────────────────────────────────────
MTX_PID=""
PUB_PID=""
cleanup() {
  echo ""
  echo "[*] Đang dừng các dịch vụ..."
  [ -n "$PUB_PID" ] && kill "$PUB_PID" 2>/dev/null || true
  [ -n "$MTX_PID" ] && kill "$MTX_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Khởi động MediaMTX ──────────────────────────────────────
echo "[*] Khởi động MediaMTX..."
"${MTX_BIN}" "${MTX_CFG}" &
MTX_PID=$!
echo "[*] MediaMTX PID: ${MTX_PID}"

# Đợi MediaMTX sẵn sàng (kiểm tra port 8554)
echo "[*] Chờ MediaMTX lắng nghe..."
for i in $(seq 1 15); do
  if ss -tlnp 2>/dev/null | grep -q ':8554'; then
    echo "[✓] MediaMTX sẵn sàng."
    break
  fi
  sleep 1
done

# ── Khởi động Python Publisher ───────────────────────────────
echo "[*] Khởi động Publisher (video + audio → RTSP)..."
python3 "${SCRIPT_DIR}/publisher.py" &
PUB_PID=$!
echo "[*] Publisher PID: ${PUB_PID}"

# ── Thông tin kết nối ────────────────────────────────────────
PI_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "======================================================"
echo "[✓] Robot Stream đang hoạt động!"
echo ""
echo "  Xem video (WebRTC):  http://${PI_IP}:8889/robot"
echo "  Gửi mic từ Browser:  http://${PI_IP}:8889/from-browser"
echo "  RTSP (nội bộ):       rtsp://${PI_IP}:8554/robot"
echo "  API MediaMTX:        http://127.0.0.1:9997/v3/paths/list"
echo ""
echo "  Nhấn Ctrl+C để dừng."
echo "======================================================"
echo ""

# Đợi bất kỳ tiến trình nào kết thúc
wait "${MTX_PID}" "${PUB_PID}"
