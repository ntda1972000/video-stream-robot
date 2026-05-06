import atexit
import logging
import os
import threading
import time
import urllib.request as urllib_req
from dataclasses import dataclass

from flask import Flask, jsonify, render_template, request

from robot_stream.config.settings_store import FPS_OPTIONS, RESOLUTION_OPTIONS, SettingsStore
from robot_stream.runtime.certificate_manager import ensure_cert
from robot_stream.runtime.network_monitor import NetworkMonitor
from robot_stream.runtime.process_supervisor import RuntimeProcessSupervisor


@dataclass
class AppContext:
    settings_store: SettingsStore
    process_supervisor: RuntimeProcessSupervisor
    net_monitor: NetworkMonitor | None
    control_state: dict


def _status_net(net_monitor: NetworkMonitor | None) -> dict:
    if net_monitor:
        return net_monitor.stats()
    return {"iface": None, "tx_kbps": 0.0, "rx_kbps": 0.0}


def _start_runtime(context: AppContext) -> None:
    context.process_supervisor.cleanup_stale_processes()
    context.process_supervisor.start_all()
    context.net_monitor = NetworkMonitor()

    def _watchdog() -> None:
        while True:
            time.sleep(5)
            context.process_supervisor.ensure_running()

    threading.Thread(target=_watchdog, daemon=True, name="watchdog").start()


def create_app(project_root: str) -> tuple[Flask, AppContext, str, str]:
    app = Flask(__name__, template_folder=os.path.join(project_root, "templates"))

    settings_file = os.path.join(project_root, "settings.json")
    settings_store = SettingsStore(settings_file)
    settings_store.load()
    settings = settings_store.data

    supervisor = RuntimeProcessSupervisor(project_root)
    context = AppContext(
        settings_store=settings_store,
        process_supervisor=supervisor,
        net_monitor=None,
        control_state={"x": 0.0, "y": 0.0},
    )

    cert_path = os.path.join(project_root, "cert.pem")
    key_path = os.path.join(project_root, "key.pem")

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/api/status")
    def api_status():
        net = _status_net(context.net_monitor)
        ok = context.process_supervisor.mediamtx_active() and context.process_supervisor.publisher_active()
        return jsonify(
            {
                "resolution": settings["resolution"],
                "fps": settings["fps"],
                "rotation": settings.get("rotation", 0),
                "stream_mode": "webrtc",
                "mediamtx_active": context.process_supervisor.mediamtx_active(),
                "publisher_active": context.process_supervisor.publisher_active(),
                "camera_ok": ok,
                "net_iface": net["iface"],
                "net_tx_kbps": net["tx_kbps"],
                "net_rx_kbps": net["rx_kbps"],
                "io_devices": [{"name": d["name"], "state": d["state"]} for d in settings["io_devices"]],
            }
        )

    @app.route("/api/control", methods=["POST"])
    def api_control():
        data = request.get_json(silent=True) or {}
        context.control_state["x"] = max(-1.0, min(1.0, float(data.get("x", 0))))
        context.control_state["y"] = max(-1.0, min(1.0, float(data.get("y", 0))))
        return jsonify({"status": "ok", **context.control_state})

    @app.route("/api/io_toggle", methods=["POST"])
    def api_io_toggle():
        data = request.get_json(silent=True) or {}
        idx = data.get("index")
        if not isinstance(idx, int) or not (0 <= idx <= 3):
            return jsonify({"error": "index must be 0-3"}), 400
        settings["io_devices"][idx]["state"] = not settings["io_devices"][idx]["state"]
        settings_store.save()
        return jsonify({"status": "ok", "index": idx, "state": settings["io_devices"][idx]["state"]})

    @app.route("/api/io_rename", methods=["POST"])
    def api_io_rename():
        data = request.get_json(silent=True) or {}
        idx = data.get("index")
        name = str(data.get("name", "")).strip()[:32]
        if not isinstance(idx, int) or not (0 <= idx <= 3):
            return jsonify({"error": "index must be 0-3"}), 400
        settings["io_devices"][idx]["name"] = name or f"Device {idx+1}"
        settings_store.save()
        return jsonify({"status": "ok", "index": idx, "name": settings["io_devices"][idx]["name"]})

    @app.route("/api/rotation", methods=["POST"])
    def api_rotation():
        data = request.get_json(silent=True) or {}
        deg = data.get("rotation")
        if deg not in (0, 90, 180, 270):
            return jsonify({"error": "rotation must be 0, 90, 180 or 270"}), 400
        settings["rotation"] = deg
        settings_store.save()
        return jsonify({"status": "ok", "rotation": deg})

    @app.route("/api/update_settings", methods=["POST"])
    def api_update_settings():
        data = request.get_json(silent=True) or {}
        changed = False

        new_res = data.get("resolution")
        if new_res and list(new_res) in RESOLUTION_OPTIONS:
            settings["resolution"] = list(new_res)
            changed = True

        new_fps = data.get("fps")
        if new_fps is not None and int(new_fps) in FPS_OPTIONS:
            settings["fps"] = int(new_fps)
            changed = True

        if changed:
            settings_store.save()
            context.process_supervisor.restart_publisher()

        return jsonify({"status": "ok", "resolution": settings["resolution"], "fps": settings["fps"]})

    def _proxy_mtx(url: str):
        try:
            req = urllib_req.Request(
                url,
                data=request.data,
                headers={"Content-Type": "application/sdp"},
                method="POST",
            )
            with urllib_req.urlopen(req, timeout=12) as response:
                body = response.read()
                return body, response.status, {"Content-Type": "application/sdp", "Access-Control-Allow-Origin": "*"}
        except Exception as exc:
            logging.warning("MTX proxy error (%s): %s", url, exc)
            return str(exc), 502

    @app.route("/proxy/whep", methods=["POST"])
    def proxy_whep():
        return _proxy_mtx("http://127.0.0.1:8889/robot/whep")

    @app.route("/proxy/whip", methods=["POST"])
    def proxy_whip():
        return _proxy_mtx("http://127.0.0.1:8889/from-browser/whip")

    atexit.register(context.process_supervisor.stop_all)
    app.config["robot_context"] = context
    app.config["robot_project_root"] = project_root

    return app, context, cert_path, key_path


def run_server(project_root: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app, context, cert_path, key_path = create_app(project_root)
    ensure_cert(cert_path, key_path)

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

    _GunicornApp(
        app,
        {
            "bind": "0.0.0.0:5000",
            "workers": 1,
            "threads": 8,
            "worker_class": "gthread",
            "certfile": cert_path,
            "keyfile": key_path,
            "timeout": 120,
            "keepalive": 2,
            "loglevel": "warning",
            "post_worker_init": lambda w: _start_runtime(context),
        },
    ).run()
