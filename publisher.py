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
from dataclasses import dataclass

# ── Cấu hình ──────────────────────────────────────────────────
RTSP_URL      = "rtsp://localhost:8554/robot"
AUDIO_BITRATE = "32k"
ALSA_MIC      = "default"   # 'hw:1,0' cho USB mic; bỏ qua nếu không có mic

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


@dataclass(frozen=True)
class VideoSettings:
    width: int
    height: int
    fps: int


def load_video_settings(settings_file: str) -> VideoSettings:
    try:
        with open(settings_file) as cfg:
            data = json.load(cfg)
        width, height = list(data.get("resolution", [640, 480]))
        fps = int(data.get("fps", 20))
        return VideoSettings(width=width, height=height, fps=fps)
    except Exception:
        return VideoSettings(width=640, height=480, fps=20)


def compute_video_bitrate(width: int, height: int, fps: int) -> str:
    # 640x480@30 = 500 kbps baseline; clamp to 80k..500k
    pixels = width * height * fps
    baseline = 640 * 480 * 30
    return str(max(80, min(500, int(pixels / baseline * 500)))) + "k"


VIDEO_SETTINGS = load_video_settings(_SETTINGS_FILE)
VIDEO_BITRATE = compute_video_bitrate(VIDEO_SETTINGS.width, VIDEO_SETTINGS.height, VIDEO_SETTINGS.fps)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("publisher")
log.info(
    "Resolution: %dx%d  FPS: %d  VIDEO_BITRATE: %s",
    VIDEO_SETTINGS.width,
    VIDEO_SETTINGS.height,
    VIDEO_SETTINGS.fps,
    VIDEO_BITRATE,
)


# ── Phát hiện lệnh capture camera ─────────────────────────────
def detect_camera_cmd(settings: VideoSettings) -> list[str]:
    """Trả về lệnh rpicam-vid hoặc libcamera-vid."""
    for name in ("rpicam-vid", "libcamera-vid"):
        if shutil.which(name):
            log.info(f"Dùng camera tool: {name}")
            return [
                name,
                "-t", "0",          # chạy mãi
                "-n",               # không preview
                "--width",  str(settings.width),
                "--height", str(settings.height),
                "--framerate", str(settings.fps),
                "--codec", "yuv420",
                "-o", "-",          # stdout
            ]
    log.error("Không tìm thấy rpicam-vid hoặc libcamera-vid!")
    sys.exit(1)


# ── Phát hiện bộ mã hóa hardware ──────────────────────────────
def detect_video_encoder() -> str:
    # Always use libx264 (CPU encoder).
    # Hardware encoders (h264_v4l2m2m, h264_omx) are NOT tested because the
    # bcm2835_codec test can deadlock the VCHIQ mutex, corrupting the kernel
    # codec state for the entire session and preventing rpicam-vid from
    # capturing frames (even for YUV output which also uses the ISP/codec path).
    log.info("Dùng bộ mã hóa: libx264 (CPU).")
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
def build_ffmpeg_command(settings: VideoSettings, encoder: str, with_audio: bool) -> list[str]:
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
        "-s",      f"{settings.width}x{settings.height}",
        "-r",      str(settings.fps),
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
    cam_cmd = detect_camera_cmd(VIDEO_SETTINGS)
    encoder = detect_video_encoder()
    audio   = has_alsa_mic()
    if not audio:
        log.warning("Không tìm thấy mic — phát video không có âm thanh.")
    ffmpeg_cmd = build_ffmpeg_command(VIDEO_SETTINGS, encoder, audio)

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
