import os
import time
import threading
import json
import logging
import subprocess
import atexit
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

def load_settings():
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in saved:
                    saved[k] = v
            saved["resolution"] = list(saved["resolution"])
            settings = saved
            return
        except Exception:
            pass
    settings = dict(DEFAULT_SETTINGS)
    # Ensure io_devices always has 4 entries
    settings["io_devices"] = [{"name": f"Device {i+1}", "state": False} for i in range(4)]

load_settings()

RESOLUTION_OPTIONS = [[320, 240], [640, 480]]
FPS_OPTIONS = [5, 10, 15, 20, 25, 30]

def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logging.warning(f"Could not save settings: {e}")

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

_mtx_proc = None
_pub_proc = None
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

def start_mediamtx():
    global _mtx_proc
    if _mtx_proc and _mtx_proc.poll() is None:
        return
    if not os.path.exists(_MTX_BIN):
        logging.warning(f"mediamtx not found: {_MTX_BIN}")
        return
    _write_mtx_config()
    log = open(os.path.join(_BASE, "mediamtx.log"), "w")
    _mtx_proc = subprocess.Popen([_MTX_BIN, _MTX_CFG], stdout=log, stderr=log)
    logging.info(f"MediaMTX started PID={_mtx_proc.pid}")

def stop_mediamtx():
    global _mtx_proc
    if _mtx_proc and _mtx_proc.poll() is None:
        _mtx_proc.terminate()
        try: _mtx_proc.wait(timeout=3)
        except subprocess.TimeoutExpired: _mtx_proc.kill()
    _mtx_proc = None

def mediamtx_active():
    return _mtx_proc is not None and _mtx_proc.poll() is None

# ---------------------------------------------------------------------------
# PUBLISHER — launch publisher.py as a fully detached subprocess
# ---------------------------------------------------------------------------
def start_publisher():
    global _pub_proc
    if _pub_proc and _pub_proc.poll() is None:
        return
    if not os.path.exists(_PUB_SCRIPT):
        logging.warning(f"publisher.py not found: {_PUB_SCRIPT}")
        return
    log = open(os.path.join(_BASE, "publisher.log"), "w")
    # Launch with its own process group so it doesn't share our terminal
    _pub_proc = subprocess.Popen(
        ["python3", _PUB_SCRIPT],
        stdout=log, stderr=log,
        start_new_session=True,
    )
    logging.info(f"Publisher started PID={_pub_proc.pid}")

def stop_publisher():
    global _pub_proc
    if _pub_proc and _pub_proc.poll() is None:
        _pub_proc.terminate()
        try: _pub_proc.wait(timeout=5)
        except subprocess.TimeoutExpired: _pub_proc.kill()
    _pub_proc = None

def publisher_active():
    return _pub_proc is not None and _pub_proc.poll() is None

atexit.register(stop_mediamtx)
atexit.register(stop_publisher)

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
        if not mediamtx_active():
            logging.warning("MediaMTX died — restarting")
            stop_mediamtx()
            start_mediamtx()
            time.sleep(2)
        if not publisher_active():
            logging.warning("Publisher died — restarting")
            start_publisher()


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
    start_mediamtx()
    time.sleep(2)
    start_publisher()
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
    save_settings()
    return jsonify({"status": "ok", "index": idx, "state": settings["io_devices"][idx]["state"]})

@app.route("/api/io_rename", methods=["POST"])
def api_io_rename():
    d   = request.get_json(silent=True) or {}
    idx  = d.get("index")
    name = str(d.get("name", "")).strip()[:32]
    if not isinstance(idx, int) or not (0 <= idx <= 3):
        return jsonify({"error": "index must be 0-3"}), 400
    settings["io_devices"][idx]["name"] = name or f"Device {idx+1}"
    save_settings()
    return jsonify({"status": "ok", "index": idx, "name": settings["io_devices"][idx]["name"]})

@app.route("/api/rotation", methods=["POST"])
def api_rotation():
    d = request.get_json(silent=True) or {}
    deg = d.get("rotation")
    if deg not in (0, 90, 180, 270):
        return jsonify({"error": "rotation must be 0, 90, 180 or 270"}), 400
    settings["rotation"] = deg
    save_settings()
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
        save_settings()
        stop_publisher()
        time.sleep(0.5)
        start_publisher()
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
