#!/usr/bin/env python3
"""
publisher.py — Đẩy Video (Camera) + Audio (Mic) lên MediaMTX qua RTSP.

Luồng dữ liệu:
  Pi Camera (CSI / libcamera)  ──┐
                                  ├─► FFmpeg ──► RTSP rtsp://localhost:8554/robot
  USB Mic (ALSA, tuỳ chọn)    ──┘

Sử dụng rpicam-vid / libcamera-vid để capture CSI camera thay vì OpenCV.
"""

import subprocess
import sys
import logging
import signal
import shutil
import json
import os

# ── Cấu hình ──────────────────────────────────────────────────
RTSP_URL      = "rtsp://localhost:8554/robot"
AUDIO_BITRATE = "32k"
ALSA_MIC      = "default"   # 'hw:1,0' cho USB mic; bỏ qua nếu không có mic

# Read resolution/fps from settings.json if available
_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
try:
    with open(_SETTINGS_FILE) as _f:
        _s = json.load(_f)
    WIDTH, HEIGHT = list(_s.get("resolution", [640, 480]))
    FPS = int(_s.get("fps", 20))
except Exception:
    WIDTH, HEIGHT = 640, 480
    FPS = 20

# Compute bitrate proportionally: 640x480@30 = 500 kbps baseline
# Scale by (pixels × fps) relative to baseline, clamped 80k–500k
_pixels   = WIDTH * HEIGHT * FPS
_baseline = 640 * 480 * 30   # = 9,216,000
VIDEO_BITRATE = str(max(80, min(500, int(_pixels / _baseline * 500)))) + "k"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("publisher")
log.info("Resolution: %dx%d  FPS: %d  VIDEO_BITRATE: %s", WIDTH, HEIGHT, FPS, VIDEO_BITRATE)


# ── Phát hiện lệnh capture camera ─────────────────────────────
def detect_camera_cmd() -> list[str]:
    """Trả về lệnh rpicam-vid hoặc libcamera-vid."""
    for name in ("rpicam-vid", "libcamera-vid"):
        if shutil.which(name):
            log.info(f"Dùng camera tool: {name}")
            return [
                name,
                "-t", "0",          # chạy mãi
                "-n",               # không preview
                "--width",  str(WIDTH),
                "--height", str(HEIGHT),
                "--framerate", str(FPS),
                "--codec", "yuv420",
                "-o", "-",          # stdout
            ]
    log.error("Không tìm thấy rpicam-vid hoặc libcamera-vid!")
    sys.exit(1)


# ── Phát hiện bộ mã hóa hardware ──────────────────────────────
def detect_video_encoder() -> str:
    candidates = [
        ("h264_v4l2m2m", ["-f", "lavfi", "-i", "nullsrc", "-t", "0.1",
                          "-c:v", "h264_v4l2m2m", "-f", "null", "-"]),
        ("h264_omx",     ["-f", "lavfi", "-i", "nullsrc", "-t", "0.1",
                          "-c:v", "h264_omx",     "-f", "null", "-"]),
    ]
    for name, test_args in candidates:
        try:
            r = subprocess.run(
                ["ffmpeg", "-loglevel", "error"] + test_args,
                capture_output=True, timeout=5,
            )
            if r.returncode == 0:
                log.info(f"Dùng bộ mã hóa hardware: {name}")
                return name
        except Exception:
            pass
    log.warning("Không có hardware encoder, dùng libx264 (CPU).")
    return "libx264"


# ── Kiểm tra mic ALSA ─────────────────────────────────────────
def has_alsa_mic() -> bool:
    try:
        r = subprocess.run(
            ["arecord", "-l"], capture_output=True, timeout=3,
        )
        return b"card" in r.stdout
    except Exception:
        return False


# ── Xây dựng lệnh FFmpeg ──────────────────────────────────────
def build_ffmpeg_command(encoder: str, with_audio: bool) -> list[str]:
    extra_video: list[str] = []
    if encoder == "h264_omx":
        extra_video = ["-zerocopy", "1"]
    elif encoder == "libx264":
        extra_video = ["-preset", "ultrafast", "-tune", "zerolatency"]

    cmd = [
        "ffmpeg", "-loglevel", "warning",
        # Video từ pipe (YUV420 từ rpicam-vid)
        "-f",      "rawvideo",
        "-pix_fmt", "yuv420p",
        "-s",      f"{WIDTH}x{HEIGHT}",
        "-r",      str(FPS),
        "-i",      "pipe:0",
    ]

    if with_audio:
        cmd += [
            "-f",  "alsa",
            "-ac", "1",
            "-ar", "44100",
            "-i",  ALSA_MIC,
        ]

    cmd += [
        "-c:v", encoder,
        "-b:v", VIDEO_BITRATE,
        *extra_video,
    ]

    if with_audio:
        cmd += [
            "-c:a", "libopus",
            "-b:a", AUDIO_BITRATE,
            "-application", "voip",
        ]
    else:
        cmd += ["-an"]

    cmd += ["-f", "rtsp", "-rtsp_transport", "tcp", RTSP_URL]
    return cmd


def main() -> None:
    cam_cmd = detect_camera_cmd()
    encoder = detect_video_encoder()
    audio   = has_alsa_mic()
    if not audio:
        log.warning("Không tìm thấy mic — phát video không có âm thanh.")
    ffmpeg_cmd = build_ffmpeg_command(encoder, audio)

    log.info(f"Khởi động camera: {' '.join(cam_cmd)}")
    cam_proc = subprocess.Popen(cam_cmd, stdout=subprocess.PIPE)

    log.info(f"Khởi động FFmpeg → {RTSP_URL}")
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=cam_proc.stdout)
    # Cho phép cam_proc nhận SIGPIPE khi ffmpeg tắt
    cam_proc.stdout.close()

    def _shutdown(sig, frame):
        log.info("Đang dừng publisher...")
        cam_proc.terminate()
        ffmpeg_proc.terminate()
        try:
            cam_proc.wait(timeout=5)
            ffmpeg_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cam_proc.kill()
            ffmpeg_proc.kill()
        log.info("Đã dừng.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Đang phát... Nhấn Ctrl+C để dừng.")
    ffmpeg_proc.wait()
    log.warning("FFmpeg đã thoát, dừng camera...")
    cam_proc.terminate()


if __name__ == "__main__":
    main()
