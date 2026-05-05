import atexit
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional


class RuntimeProcessSupervisor:
    """Owns MediaMTX and publisher subprocess lifecycle management."""

    def __init__(self, project_root: str):
        self._project_root = project_root
        self._mtx_bin = os.path.join(project_root, "mediamtx", "mediamtx")
        self._mtx_cfg = os.path.join(project_root, "mediamtx_run.yml")
        self._publisher_script = os.path.join(project_root, "publisher.py")
        self._mtx_proc: Optional[subprocess.Popen] = None
        self._publisher_proc: Optional[subprocess.Popen] = None
        self._mtx_log = None
        self._publisher_log = None
        self._watchdog_started = False
        self._watchdog_lock = threading.Lock()

        atexit.register(self.stop_mediamtx)
        atexit.register(self.stop_publisher)

    def cleanup_leftovers(self) -> None:
        for command in (["pkill", "-x", "mediamtx"], ["pkill", "-x", "mtxrpicam"], ["pkill", "-f", "publisher.py"]):
            subprocess.run(command, capture_output=True)

    def _collect_non_loopback_ips(self) -> list[str]:
        ips = []
        try:
            output = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True)
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1] != "lo":
                    ip = parts[3].split("/")[0]
                    if ip not in ips:
                        ips.append(ip)
        except Exception:
            pass
        return ips

    def write_mediamtx_config(self) -> None:
        ips = self._collect_non_loopback_ips()
        ice_hosts = "[" + ", ".join(ips) + "]" if ips else "[]"

        with open(self._mtx_cfg, "w", encoding="utf-8") as config_file:
            config_file.write(
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
webrtcAdditionalHosts: {ice_hosts}
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

        self.write_mediamtx_config()
        self._mtx_log = open(os.path.join(self._project_root, "mediamtx.log"), "w", encoding="utf-8")
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

        if not os.path.exists(self._publisher_script):
            logging.warning("publisher.py not found: %s", self._publisher_script)
            return

        python_executable = os.environ.get("PYTHON_EXECUTABLE", sys.executable or "python3")
        self._publisher_log = open(os.path.join(self._project_root, "publisher.log"), "w", encoding="utf-8")
        self._publisher_proc = subprocess.Popen(
            [python_executable, self._publisher_script],
            stdout=self._publisher_log,
            stderr=self._publisher_log,
            start_new_session=True,
        )
        logging.info("Publisher started PID=%s", self._publisher_proc.pid)

    def stop_publisher(self) -> None:
        if self._publisher_proc and self._publisher_proc.poll() is None:
            self._publisher_proc.terminate()
            try:
                self._publisher_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._publisher_proc.kill()

        self._publisher_proc = None
        if self._publisher_log:
            self._publisher_log.close()
            self._publisher_log = None

    def publisher_active(self) -> bool:
        return self._publisher_proc is not None and self._publisher_proc.poll() is None

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
                logging.warning("MediaMTX exited unexpectedly, restarting")
                self.stop_mediamtx()
                self.start_mediamtx()
                time.sleep(2)
            if not self.publisher_active():
                logging.warning("Publisher exited unexpectedly, restarting")
                self.start_publisher()

    def start_watchdog(self) -> None:
        with self._watchdog_lock:
            if self._watchdog_started:
                return
            threading.Thread(target=self._watchdog_loop, daemon=True, name="runtime-watchdog").start()
            self._watchdog_started = True
