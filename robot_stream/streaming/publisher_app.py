import json
import logging
import os
import shutil
import signal
import subprocess
import sys

RTSP_URL = "rtsp://localhost:8554/robot"
AUDIO_BITRATE = "32k"
ALSA_MIC = "default"
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_FPS = 20
MIN_VIDEO_KBPS = 80
MAX_VIDEO_KBPS = 500


def _settings_file(project_root: str) -> str:
    return os.path.join(project_root, "settings.json")


def load_video_settings(project_root: str) -> tuple[int, int, int]:
    """Load stream width/height/fps from settings with fallback defaults."""
    width, height, fps = DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_FPS

    try:
        with open(_settings_file(project_root), "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)

        resolution = settings.get("resolution", [DEFAULT_WIDTH, DEFAULT_HEIGHT])
        if isinstance(resolution, (list, tuple)) and len(resolution) == 2:
            width = int(resolution[0])
            height = int(resolution[1])
        fps = int(settings.get("fps", DEFAULT_FPS))
    except Exception as exc:
        logging.getLogger("publisher").warning("Could not read settings.json, using defaults: %s", exc)

    return width, height, fps


def compute_video_bitrate(width: int, height: int, fps: int) -> str:
    pixels = width * height * fps
    baseline = 640 * 480 * 30
    kbps = int(pixels / baseline * MAX_VIDEO_KBPS)
    return f"{max(MIN_VIDEO_KBPS, min(MAX_VIDEO_KBPS, kbps))}k"


def detect_camera_command(width: int, height: int, fps: int, logger: logging.Logger) -> list[str]:
    for name in ("rpicam-vid", "libcamera-vid"):
        if shutil.which(name):
            logger.info("Using camera tool: %s", name)
            return [
                name,
                "-t",
                "0",
                "-n",
                "--width",
                str(width),
                "--height",
                str(height),
                "--framerate",
                str(fps),
                "--codec",
                "yuv420",
                "-o",
                "-",
            ]

    logger.error("Camera capture tool not found (rpicam-vid/libcamera-vid)")
    sys.exit(1)


def detect_video_encoder(logger: logging.Logger) -> str:
    candidates = [
        ("h264_v4l2m2m", ["-f", "lavfi", "-i", "nullsrc", "-t", "0.1", "-c:v", "h264_v4l2m2m", "-f", "null", "-"]),
        ("h264_omx", ["-f", "lavfi", "-i", "nullsrc", "-t", "0.1", "-c:v", "h264_omx", "-f", "null", "-"]),
    ]

    for name, test_args in candidates:
        try:
            result = subprocess.run(["ffmpeg", "-loglevel", "error"] + test_args, capture_output=True, timeout=5)
            if result.returncode == 0:
                logger.info("Using hardware encoder: %s", name)
                return name
        except Exception:
            pass

    logger.warning("No hardware encoder available, using libx264")
    return "libx264"


def has_alsa_mic() -> bool:
    try:
        result = subprocess.run(["arecord", "-l"], capture_output=True, timeout=3)
        return b"card" in result.stdout
    except Exception:
        return False


def build_ffmpeg_command(
    width: int,
    height: int,
    fps: int,
    encoder: str,
    with_audio: bool,
    video_bitrate: str,
) -> list[str]:
    extra_video: list[str] = []
    if encoder == "h264_omx":
        extra_video = ["-zerocopy", "1"]
    elif encoder == "libx264":
        extra_video = ["-preset", "ultrafast", "-tune", "zerolatency"]

    command = [
        "ffmpeg",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "yuv420p",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
    ]

    if with_audio:
        command += ["-f", "alsa", "-ac", "1", "-ar", "44100", "-i", ALSA_MIC]

    command += ["-c:v", encoder, "-b:v", video_bitrate, *extra_video]

    if with_audio:
        command += ["-c:a", "libopus", "-b:a", AUDIO_BITRATE, "-application", "voip"]
    else:
        command += ["-an"]

    command += ["-f", "rtsp", "-rtsp_transport", "tcp", RTSP_URL]
    return command


def run_publisher(project_root: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("publisher")

    width, height, fps = load_video_settings(project_root)
    video_bitrate = compute_video_bitrate(width, height, fps)

    logger.info("Resolution: %dx%d  FPS: %d  VIDEO_BITRATE: %s", width, height, fps, video_bitrate)

    camera_command = detect_camera_command(width, height, fps, logger)
    encoder = detect_video_encoder(logger)
    with_audio = has_alsa_mic()

    if not with_audio:
        logger.warning("No ALSA microphone detected, streaming video without audio")

    ffmpeg_command = build_ffmpeg_command(width, height, fps, encoder, with_audio, video_bitrate)

    logger.info("Starting camera: %s", " ".join(camera_command))
    camera_process = subprocess.Popen(camera_command, stdout=subprocess.PIPE)

    logger.info("Starting FFmpeg -> %s", RTSP_URL)
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=camera_process.stdout)
    camera_process.stdout.close()

    def shutdown_handler(sig, frame):
        logger.info("Stopping publisher")
        camera_process.terminate()
        ffmpeg_process.terminate()
        try:
            camera_process.wait(timeout=5)
            ffmpeg_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            camera_process.kill()
            ffmpeg_process.kill()
        logger.info("Publisher stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("Streaming... Press Ctrl+C to stop")
    ffmpeg_process.wait()
    logger.warning("FFmpeg exited, stopping camera process")
    camera_process.terminate()
