import os
import time
import threading
import json
import logging
import subprocess
import atexit
from typing import Callable
import urllib.request as _urllib_req
from flask import Flask, render_template, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
DEFAULT_SETTINGS = {
    "resolution": [640, 480],
    "fps": 20,
    "rotation": 0,
    "io_devices": [
        {"name": "Device 1", "state": False},
        {"name": "Device 2", "state": False},
        {"name": "Device 3", "state": False},
        {"name": "Device 4", "state": False},
    ],
}


class SettingsStore:
    def __init__(self, settings_file: str, default_settings: dict):
        self._settings_file = settings_file
        self._default_settings = default_settings
        self._data = self._build_default()

    def _build_default(self) -> dict:
        data = dict(self._default_settings)
        data["io_devices"] = [{"name": f"Device {i+1}", "state": False} for i in range(4)]
        return data

    def load(self) -> None:
        if os.path.exists(self._settings_file):
            try:
                with open(self._settings_file) as f:
                    saved = json.load(f)
                for key, value in self._default_settings.items():
                    if key not in saved:
                        saved[key] = value
                saved["resolution"] = list(saved["resolution"])
                saved["io_devices"] = list(saved.get("io_devices", []))[:4]
                while len(saved["io_devices"]) < 4:
                    idx = len(saved["io_devices"]) + 1
                    saved["io_devices"].append({"name": f"Device {idx}", "state": False})
                self._data = saved
                return
            except Exception:
                pass
        self._data = self._build_default()

    def save(self) -> None:
        try:
            with open(self._settings_file, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as exc:
            logging.warning("Could not save settings: %s", exc)

    @property
    def data(self) -> dict:
        return self._data


settings_store = SettingsStore(SETTINGS_FILE, DEFAULT_SETTINGS)
settings_store.load()
settings = settings_store.data

RESOLUTION_OPTIONS = [[320, 240], [640, 480]]
FPS_OPTIONS = [5, 10, 15, 20, 25, 30]

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
_BASE       = os.path.dirname(os.path.abspath(__file__))
_MTX_BIN    = os.path.join(_BASE, "..", "rc-car", "mediamtx")
_MTX_CFG    = os.path.join(_BASE, "mediamtx_run.yml")
_PUB_SCRIPT = os.path.join(_BASE, "publisher.py")
_CERT       = os.path.join(_BASE, "cert.pem")
_KEY        = os.path.join(_BASE, "key.pem")

def _ensure_cert():
    """Generate a self-signed TLS certificate covering all current IPs (LAN + Tailscale)."""
    # Collect all non-loopback IPv4 addresses
    try:
        out = subprocess.check_output(['ip', '-4', '-o', 'addr'], text=True)
        all_ips = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != 'lo':
                all_ips.append(parts[3].split('/')[0])
    except Exception:
        all_ips = []
    if not all_ips:
        all_ips = ['127.0.0.1']

    san = ','.join(f'IP:{ip}' for ip in all_ips)

    # Regenerate if cert is missing or doesn't cover all current IPs
    needs_regen = not (os.path.exists(_CERT) and os.path.exists(_KEY))
    if not needs_regen:
        try:
            cert_text = subprocess.check_output(
                ['openssl', 'x509', '-in', _CERT, '-noout', '-text'], text=True)
            needs_regen = any(ip not in cert_text for ip in all_ips)
        except Exception:
            needs_regen = True

    if not needs_regen:
        return

    logging.info("Generating self-signed TLS certificate for IPs: %s", all_ips)
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", _KEY, "-out", _CERT,
        "-days", "3650", "-nodes",
        "-subj", "/CN=robot-pi",
        "-addext", f"subjectAltName={san}",
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logging.info("Certificate written: %s", san)

_STREAM_PATH = "robot"  # must match publisher.py RTSP_URL path

# ---------------------------------------------------------------------------
# MEDIAMTX — RTSP in + WebRTC out
# ---------------------------------------------------------------------------
def _write_mtx_config():
    _ips = []
    try:
        out = subprocess.check_output(['ip', '-4', '-o', 'addr'], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != 'lo':
                ip = parts[3].split('/')[0]
                if ip not in _ips:
                    _ips.append(ip)
    except Exception:
        pass
    ice = '[' + ', '.join(_ips) + ']' if _ips else '[]'
    with open(_MTX_CFG, "w") as f:
        f.write(f"""logLevel: info
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
""")


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


def _mediamtx_exists() -> bool:
    ok = os.path.exists(_MTX_BIN)
    if not ok:
        logging.warning("mediamtx not found: %s", _MTX_BIN)
    return ok


def _publisher_exists() -> bool:
    ok = os.path.exists(_PUB_SCRIPT)
    if not ok:
        logging.warning("publisher.py not found: %s", _PUB_SCRIPT)
    return ok


def _mediamtx_command() -> list[str]:
    _write_mtx_config()
    return [_MTX_BIN, _MTX_CFG]


def _publisher_command() -> list[str]:
    return ["python3", _PUB_SCRIPT]


class RuntimeProcessSupervisor:
    def __init__(self):
        self._mediamtx = ManagedProcess(
            name="MediaMTX",
            command_factory=_mediamtx_command,
            log_path=os.path.join(_BASE, "mediamtx.log"),
            exists_check=_mediamtx_exists,
            stop_timeout=3,
        )
        self._publisher = ManagedProcess(
            name="Publisher",
            command_factory=_publisher_command,
            log_path=os.path.join(_BASE, "publisher.log"),
            exists_check=_publisher_exists,
            start_new_session=True,
            stop_timeout=5,
        )

    def start_all(self) -> None:
        self._mediamtx.start()
        time.sleep(2)
        self._publisher.start()

    def start_mediamtx(self) -> None:
        self._mediamtx.start()

    def stop_mediamtx(self) -> None:
        self._mediamtx.stop()

    def start_publisher(self) -> None:
        self._publisher.start()

    def stop_publisher(self) -> None:
        self._publisher.stop()

    def stop_all(self) -> None:
        self._publisher.stop()
        self._mediamtx.stop()

    def ensure_running(self) -> None:
        if not self._mediamtx.is_active():
            logging.warning("MediaMTX died - restarting")
            self._mediamtx.stop()
            self._mediamtx.start()
            time.sleep(2)
        if not self._publisher.is_active():
            logging.warning("Publisher died - restarting")
            self._publisher.start()

    def restart_publisher(self) -> None:
        self._publisher.stop()
        time.sleep(0.5)
        self._publisher.start()

    def mediamtx_active(self) -> bool:
        return self._mediamtx.is_active()

    def publisher_active(self) -> bool:
        return self._publisher.is_active()


process_supervisor = RuntimeProcessSupervisor()

def start_mediamtx():
    process_supervisor.start_mediamtx()

def stop_mediamtx():
    process_supervisor.stop_mediamtx()

def mediamtx_active():
    return process_supervisor.mediamtx_active()

# ---------------------------------------------------------------------------
# PUBLISHER — launch publisher.py as a fully detached subprocess
# ---------------------------------------------------------------------------
def start_publisher():
    process_supervisor.start_publisher()

def stop_publisher():
    process_supervisor.stop_publisher()

def publisher_active():
    return process_supervisor.publisher_active()

atexit.register(process_supervisor.stop_all)

# Kill any leftover processes from a previous run.
# Subprocess startup (start_mediamtx / start_publisher) is intentionally
# deferred to _start_bg_threads(), which runs in the gunicorn worker process
# AFTER fork — this ensures the worker is the proper parent of those
# subprocesses and Popen.poll() works correctly.
for sig in (["pkill", "-x", "mediamtx"], ["pkill", "-x", "mtxrpicam"],
            ["pkill", "-f", "publisher.py"]):
    subprocess.run(sig, capture_output=True)
time.sleep(1)

# ---------------------------------------------------------------------------
# WATCHDOG
# ---------------------------------------------------------------------------
def _watchdog():
    while True:
        time.sleep(5)
        process_supervisor.ensure_running()


# ---------------------------------------------------------------------------
# NETWORK MONITOR
# ---------------------------------------------------------------------------
class NetworkMonitor:
    def __init__(self):
        self._tx = self._rx = 0.0
        self._pt = self._px = self._py = 0.0
        self._iface = self._pick_iface()
        threading.Thread(target=self._loop, daemon=True).start()

    @staticmethod
    def _pick_iface():
        # 1. Use the interface of the default route (most reliable)
        try:
            out = subprocess.check_output(['ip', 'route', 'show', 'default'], text=True)
            for line in out.splitlines():
                parts = line.split()
                if 'dev' in parts:
                    dev = parts[parts.index('dev') + 1]
                    if os.path.exists(f'/sys/class/net/{dev}/statistics/tx_bytes'):
                        return dev
        except Exception:
            pass
        # 2. Fall back: pick non-loopback interface with the highest tx_bytes
        try:
            best, best_tx = None, -1
            for name in os.listdir('/sys/class/net'):
                if name == 'lo':
                    continue
                try:
                    tx = int(open(f'/sys/class/net/{name}/statistics/tx_bytes').read())
                    if tx > best_tx:
                        best_tx, best = tx, name
                except Exception:
                    pass
            return best
        except Exception:
            return None

    def _loop(self):
        while True:
            time.sleep(2)
            if not self._iface: continue
            try:
                tx = int(open(f"/sys/class/net/{self._iface}/statistics/tx_bytes").read())
                rx = int(open(f"/sys/class/net/{self._iface}/statistics/rx_bytes").read())
                now = time.time()
                if self._pt > 0 and (now - self._pt) > 0:
                    dt = now - self._pt
                    self._tx = round((tx - self._px) * 8 / (dt * 1000), 1)
                    self._rx = round((rx - self._py) * 8 / (dt * 1000), 1)
                self._pt, self._px, self._py = now, tx, rx
            except Exception:
                pass

    def stats(self):
        return {"iface": self._iface, "tx_kbps": max(0.0, self._tx), "rx_kbps": max(0.0, self._rx)}

net_monitor = None

def _start_bg_threads():
    """Start subprocesses and background threads.
    Must run inside the gunicorn WORKER (after fork) so that Popen objects
    are owned by the serving process and poll() / wait() work correctly.
    Called via gunicorn post_worker_init — do NOT call at module level."""
    global net_monitor
    process_supervisor.start_all()
    net_monitor = NetworkMonitor()
    threading.Thread(target=_watchdog, daemon=True, name="watchdog").start()

# NOTE: _start_bg_threads() is intentionally NOT called here.
# It is called only in the gunicorn worker via post_worker_init.

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    net = net_monitor.stats() if net_monitor else {"iface": None, "tx_kbps": 0.0, "rx_kbps": 0.0}
    ok  = mediamtx_active() and publisher_active()
    return jsonify({
        "resolution": settings["resolution"],
        "fps": settings["fps"],
        "rotation": settings.get("rotation", 0),
        "stream_mode": "webrtc",
        "mediamtx_active": mediamtx_active(),
        "publisher_active": publisher_active(),
        "camera_ok": ok,
        "net_iface": net["iface"],
        "net_tx_kbps": net["tx_kbps"],
        "net_rx_kbps": net["rx_kbps"],
        "io_devices": [{"name": d["name"], "state": d["state"]}
                       for d in settings["io_devices"]],
    })

_ctrl = {"x": 0.0, "y": 0.0}

@app.route("/api/control", methods=["POST"])
def api_control():
    d = request.get_json(silent=True) or {}
    _ctrl["x"] = max(-1.0, min(1.0, float(d.get("x", 0))))
    _ctrl["y"] = max(-1.0, min(1.0, float(d.get("y", 0))))
    return jsonify({"status": "ok", **_ctrl})

@app.route("/api/io_toggle", methods=["POST"])
def api_io_toggle():
    d   = request.get_json(silent=True) or {}
    idx = d.get("index")
    if not isinstance(idx, int) or not (0 <= idx <= 3):
        return jsonify({"error": "index must be 0-3"}), 400
    settings["io_devices"][idx]["state"] = not settings["io_devices"][idx]["state"]
    settings_store.save()
    return jsonify({"status": "ok", "index": idx, "state": settings["io_devices"][idx]["state"]})

@app.route("/api/io_rename", methods=["POST"])
def api_io_rename():
    d   = request.get_json(silent=True) or {}
    idx  = d.get("index")
    name = str(d.get("name", "")).strip()[:32]
    if not isinstance(idx, int) or not (0 <= idx <= 3):
        return jsonify({"error": "index must be 0-3"}), 400
    settings["io_devices"][idx]["name"] = name or f"Device {idx+1}"
    settings_store.save()
    return jsonify({"status": "ok", "index": idx, "name": settings["io_devices"][idx]["name"]})

@app.route("/api/rotation", methods=["POST"])
def api_rotation():
    d = request.get_json(silent=True) or {}
    deg = d.get("rotation")
    if deg not in (0, 90, 180, 270):
        return jsonify({"error": "rotation must be 0, 90, 180 or 270"}), 400
    settings["rotation"] = deg
    settings_store.save()
    return jsonify({"status": "ok", "rotation": deg})

@app.route("/api/update_settings", methods=["POST"])
def api_update_settings():
    d = request.get_json(silent=True) or {}
    changed = False
    new_res = d.get("resolution")
    if new_res and list(new_res) in RESOLUTION_OPTIONS:
        settings["resolution"] = list(new_res)
        changed = True
    new_fps = d.get("fps")
    if new_fps is not None and int(new_fps) in FPS_OPTIONS:
        settings["fps"] = int(new_fps)
        changed = True
    if changed:
        settings_store.save()
        process_supervisor.restart_publisher()
    return jsonify({"status": "ok", "resolution": settings["resolution"], "fps": settings["fps"]})

# ---------------------------------------------------------------------------
# WEBRTC SIGNALLING PROXY  (keeps browser on one HTTPS origin → no mixed-content)
# ---------------------------------------------------------------------------
def _proxy_mtx(url):
    try:
        req = _urllib_req.Request(
            url, data=request.data,
            headers={"Content-Type": "application/sdp"},
            method="POST")
        with _urllib_req.urlopen(req, timeout=12) as r:
            body = r.read()
            return body, r.status, {"Content-Type": "application/sdp",
                                    "Access-Control-Allow-Origin": "*"}
    except Exception as e:
        logging.warning("MTX proxy error (%s): %s", url, e)
        return str(e), 502

@app.route("/proxy/whep", methods=["POST"])
def proxy_whep():
    return _proxy_mtx("http://127.0.0.1:8889/robot/whep")

@app.route("/proxy/whip", methods=["POST"])
def proxy_whip():
    return _proxy_mtx("http://127.0.0.1:8889/from-browser/whip")

if __name__ == "__main__":
    _ensure_cert()
    logging.info("Starting HTTPS on port 5000 via gunicorn")
    import gunicorn.app.base

    class _GunicornApp(gunicorn.app.base.BaseApplication):
        def __init__(self, application, options=None):
            self.options = options or {}
            self.application = application
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    _GunicornApp(app, {
        "bind":         "0.0.0.0:5000",
        "workers":      1,
        "threads":      8,
        "worker_class": "gthread",
        "certfile":     _CERT,
        "keyfile":      _KEY,
        "timeout":      120,
        "keepalive":    2,
        "loglevel":     "warning",
        "post_worker_init": lambda w: _start_bg_threads(),
    }).run()
