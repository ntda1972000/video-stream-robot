import logging
import os
import subprocess
import time
from typing import Callable


class ManagedProcess:
    def __init__(
        self,
        name: str,
        command_factory: Callable[[], list[str]],
        log_path: str,
        exists_check: Callable[[], bool] | None = None,
        start_new_session: bool = False,
        stop_timeout: int = 5,
    ):
        self._name = name
        self._command_factory = command_factory
        self._log_path = log_path
        self._exists_check = exists_check
        self._start_new_session = start_new_session
        self._stop_timeout = stop_timeout
        self._proc = None
        self._log_handle = None

    def is_active(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if self.is_active():
            return
        if self._exists_check and not self._exists_check():
            logging.warning("%s start skipped due to missing dependency", self._name)
            return
        cmd = self._command_factory()
        self._log_handle = open(self._log_path, "w")
        self._proc = subprocess.Popen(
            cmd,
            stdout=self._log_handle,
            stderr=self._log_handle,
            start_new_session=self._start_new_session,
        )
        logging.info("%s started PID=%s", self._name, self._proc.pid)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=self._stop_timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None


class RuntimeProcessSupervisor:
    def __init__(self, project_root: str):
        self._project_root = project_root
        self._mtx_bin = os.path.join(project_root, "..", "rc-car", "mediamtx")
        self._mtx_cfg = os.path.join(project_root, "mediamtx_run.yml")
        self._publisher_script = os.path.join(project_root, "publisher.py")

        self._mediamtx = ManagedProcess(
            name="MediaMTX",
            command_factory=self._mediamtx_command,
            log_path=os.path.join(project_root, "mediamtx.log"),
            exists_check=self._mediamtx_exists,
            stop_timeout=3,
        )
        self._publisher = ManagedProcess(
            name="Publisher",
            command_factory=self._publisher_command,
            log_path=os.path.join(project_root, "publisher.log"),
            exists_check=self._publisher_exists,
            start_new_session=True,
            stop_timeout=5,
        )

    def _mediamtx_exists(self) -> bool:
        ok = os.path.exists(self._mtx_bin)
        if not ok:
            logging.warning("mediamtx not found: %s", self._mtx_bin)
        return ok

    def _publisher_exists(self) -> bool:
        ok = os.path.exists(self._publisher_script)
        if not ok:
            logging.warning("publisher.py not found: %s", self._publisher_script)
        return ok

    def _write_mtx_config(self) -> None:
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
        ice = "[" + ", ".join(ips) + "]" if ips else "[]"
        with open(self._mtx_cfg, "w") as handle:
            handle.write(
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

    def _mediamtx_command(self) -> list[str]:
        self._write_mtx_config()
        return [self._mtx_bin, self._mtx_cfg]

    def _publisher_command(self) -> list[str]:
        return ["python3", self._publisher_script]

    def cleanup_stale_processes(self) -> None:
        for sig in (["pkill", "-x", "mediamtx"], ["pkill", "-x", "mtxrpicam"], ["pkill", "-f", "publisher.py"]):
            subprocess.run(sig, capture_output=True)
        time.sleep(1)

    def start_all(self) -> None:
        self._mediamtx.start()
        time.sleep(2)
        self._publisher.start()

    def stop_all(self) -> None:
        self._publisher.stop()
        self._mediamtx.stop()

    def restart_publisher(self) -> None:
        self._publisher.stop()
        time.sleep(0.5)
        self._publisher.start()

    def ensure_running(self) -> None:
        if not self._mediamtx.is_active():
            logging.warning("MediaMTX died - restarting")
            self._mediamtx.stop()
            self._mediamtx.start()
            time.sleep(2)
        if not self._publisher.is_active():
            logging.warning("Publisher died - restarting")
            self._publisher.start()

    def mediamtx_active(self) -> bool:
        return self._mediamtx.is_active()

    def publisher_active(self) -> bool:
        return self._publisher.is_active()
