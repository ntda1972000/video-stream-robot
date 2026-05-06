import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass

RTSP_URL = "rtsp://localhost:8554/robot"
AUDIO_BITRATE = "32k"
ALSA_MIC = "default"


@dataclass(frozen=True)
class VideoSettings:
    width: int
    height: int
    fps: int


def load_video_settings(project_root: str) -> VideoSettings:
    settings_file = os.path.join(project_root, "settings.json")
    try:
        with open(settings_file) as cfg:
            data = json.load(cfg)
        width, height = list(data.get("resolution", [640, 480]))
        fps = int(data.get("fps", 20))
        return VideoSettings(width=width, height=height, fps=fps)
    except Exception:
        return VideoSettings(width=640, height=480, fps=20)


def compute_video_bitrate(width: int, height: int, fps: int) -> str:
    pixels = width * height * fps
    baseline = 640 * 480 * 30
    return str(max(80, min(500, int(pixels / baseline * 500)))) + "k"


def detect_camera_cmd(settings: VideoSettings, logger: logging.Logger) -> list[str]:
    for name in ("rpicam-vid", "libcamera-vid"):
        if shutil.which(name):
            logger.info("Using camera tool: %s", name)
            return [
                name,
                "-t",
                "0",
                "-n",
                "--width",
                str(settings.width),
                "--height",
                str(settings.height),
                "--framerate",
                str(settings.fps),
                "--codec",
                "yuv420",
                "-o",
                "-",
            ]
    logger.error("rpicam-vid or libcamera-vid was not found")
    sys.exit(1)


def detect_video_encoder(logger: logging.Logger) -> str:
    logger.info("Using encoder: libx264 (CPU)")
    return "libx264"


def has_alsa_mic() -> bool:
    try:
        result = subprocess.run(["arecord", "-l"], capture_output=True, timeout=3)
        return b"card" in result.stdout
    except Exception:
        return False


def build_ffmpeg_command(settings: VideoSettings, encoder: str, with_audio: bool, video_bitrate: str) -> list[str]:
    extra_video: list[str] = []
    if encoder == "h264_omx":
        extra_video = ["-zerocopy", "1"]
    elif encoder == "libx264":
        extra_video = ["-preset", "ultrafast", "-tune", "zerolatency"]

    cmd = [
        "ffmpeg",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "yuv420p",
        "-s",
        f"{settings.width}x{settings.height}",
        "-r",
        str(settings.fps),
        "-i",
        "pipe:0",
    ]

    if with_audio:
        cmd += ["-f", "alsa", "-ac", "1", "-ar", "44100", "-i", ALSA_MIC]

    cmd += ["-c:v", encoder, "-b:v", video_bitrate, *extra_video]

    if with_audio:
        cmd += ["-c:a", "libopus", "-b:a", AUDIO_BITRATE, "-application", "voip"]
    else:
        cmd += ["-an"]

    cmd += ["-f", "rtsp", "-rtsp_transport", "tcp", RTSP_URL]
    return cmd


def run_publisher(project_root: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("publisher")

    settings = load_video_settings(project_root)
    video_bitrate = compute_video_bitrate(settings.width, settings.height, settings.fps)
    logger.info(
        "Resolution: %dx%d FPS: %d VIDEO_BITRATE: %s",
        settings.width,
        settings.height,
        settings.fps,
        video_bitrate,
    )

    cam_cmd = detect_camera_cmd(settings, logger)
    encoder = detect_video_encoder(logger)
    audio = has_alsa_mic()
    if not audio:
        logger.warning("Microphone not found, streaming without audio")

    ffmpeg_cmd = build_ffmpeg_command(settings, encoder, audio, video_bitrate)

    logger.info("Starting camera: %s", " ".join(cam_cmd))
    cam_proc = subprocess.Popen(cam_cmd, stdout=subprocess.PIPE)

    logger.info("Starting FFmpeg -> %s", RTSP_URL)
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=cam_proc.stdout)
    cam_proc.stdout.close()

    def _shutdown(sig, frame):
        logger.info("Stopping publisher...")
        cam_proc.terminate()
        ffmpeg_proc.terminate()
        try:
            cam_proc.wait(timeout=5)
            ffmpeg_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cam_proc.kill()
            ffmpeg_proc.kill()
        logger.info("Stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Streaming started. Press Ctrl+C to stop")
    ffmpeg_proc.wait()
    logger.warning("FFmpeg exited, stopping camera")
    cam_proc.terminate()
