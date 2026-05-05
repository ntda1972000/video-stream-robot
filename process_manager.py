import atexit
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional


class RuntimeProcessManager:
    """Manages MediaMTX and publisher subprocess lifecycles."""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._mtx_bin = os.path.join(base_dir, "..", "rc-car", "mediamtx")
        self._mtx_cfg = os.path.join(base_dir, "mediamtx_run.yml")
        self._pub_script = os.path.join(base_dir, "publisher.py")
        self._mtx_proc: Optional[subprocess.Popen] = None
        self._pub_proc: Optional[subprocess.Popen] = None
        self._mtx_log = None
        self._pub_log = None
        self._watchdog_started = False
        self._watchdog_lock = threading.Lock()

        atexit.register(self.stop_mediamtx)
        atexit.register(self.stop_publisher)

    def cleanup_leftovers(self) -> None:
        for sig in (["pkill", "-x", "mediamtx"], ["pkill", "-x", "mtxrpicam"], ["pkill", "-f", "publisher.py"]):
            subprocess.run(sig, capture_output=True)

    def _collect_non_loopback_ips(self) -> list[str]:
        ips = []
        try:
            out = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1] != "lo":
                    ip = parts[3].split("/")[0]
                    if ip not in ips:
                        ips.append(ip)
        except Exception:
            pass
        return ips

    def write_mtx_config(self) -> None:
        ips = self._collect_non_loopback_ips()
        ice = "[" + ", ".join(ips) + "]" if ips else "[]"
        with open(self._mtx_cfg, "w", encoding="utf-8") as f:
            f.write(
                f"""logLevel: info
logDestinations: [stdout]
api: yes
apiAddress: 127.0.0.1:9997
metrics: no
rtsp: yes
rtspTransports: [tcp]
rtspAddress: :8554
rtmp: no
hls: no
srt: no
webrtc: yes
webrtcAddress: :8889
webrtcICEServers2: []
webrtcAdditionalHosts: {ice}
paths:
  robot:
    source: publisher
  from-browser:
    runOnReady: >-
      ffmpeg -loglevel warning
      -i rtsp://127.0.0.1:8554/from-browser
      -af aresample=48000
      -f pulse default
    runOnReadyRestart: yes
"""
            )

    def start_mediamtx(self) -> None:
        if self.mediamtx_active():
            return
        if not os.path.exists(self._mtx_bin):
            logging.warning("mediamtx not found: %s", self._mtx_bin)
            return

        self.write_mtx_config()
        self._mtx_log = open(os.path.join(self._base_dir, "mediamtx.log"), "w", encoding="utf-8")
        self._mtx_proc = subprocess.Popen([self._mtx_bin, self._mtx_cfg], stdout=self._mtx_log, stderr=self._mtx_log)
        logging.info("MediaMTX started PID=%s", self._mtx_proc.pid)

    def stop_mediamtx(self) -> None:
        if self._mtx_proc and self._mtx_proc.poll() is None:
            self._mtx_proc.terminate()
            try:
                self._mtx_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._mtx_proc.kill()
        self._mtx_proc = None
        if self._mtx_log:
            self._mtx_log.close()
            self._mtx_log = None

    def mediamtx_active(self) -> bool:
        return self._mtx_proc is not None and self._mtx_proc.poll() is None

    def start_publisher(self) -> None:
        if self.publisher_active():
            return
        if not os.path.exists(self._pub_script):
            logging.warning("publisher.py not found: %s", self._pub_script)
            return

        python_exec = os.environ.get("PYTHON_EXECUTABLE", sys.executable or "python3")
        self._pub_log = open(os.path.join(self._base_dir, "publisher.log"), "w", encoding="utf-8")
        self._pub_proc = subprocess.Popen(
            [python_exec, self._pub_script],
            stdout=self._pub_log,
            stderr=self._pub_log,
            start_new_session=True,
        )
        logging.info("Publisher started PID=%s", self._pub_proc.pid)

    def stop_publisher(self) -> None:
        if self._pub_proc and self._pub_proc.poll() is None:
            self._pub_proc.terminate()
            try:
                self._pub_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._pub_proc.kill()
        self._pub_proc = None
        if self._pub_log:
            self._pub_log.close()
            self._pub_log = None

    def publisher_active(self) -> bool:
        return self._pub_proc is not None and self._pub_proc.poll() is None

    def restart_publisher(self) -> None:
        self.stop_publisher()
        time.sleep(0.5)
        self.start_publisher()

    def start_all(self) -> None:
        self.cleanup_leftovers()
        time.sleep(1)
        self.start_mediamtx()
        time.sleep(2)
        self.start_publisher()

    def _watchdog_loop(self) -> None:
        while True:
            time.sleep(5)
            if not self.mediamtx_active():
                logging.warning("MediaMTX died - restarting")
                self.stop_mediamtx()
                self.start_mediamtx()
                time.sleep(2)
            if not self.publisher_active():
                logging.warning("Publisher died - restarting")
                self.start_publisher()

    def start_watchdog(self) -> None:
        with self._watchdog_lock:
            if self._watchdog_started:
                return
            threading.Thread(target=self._watchdog_loop, daemon=True, name="watchdog").start()
            self._watchdog_started = True
