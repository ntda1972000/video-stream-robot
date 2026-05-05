import logging
import os
import urllib.request as _urllib_req

from flask import Flask, jsonify, render_template, request

from app_state import AppState
from cert_manager import ensure_cert
from exceptions import ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

_BASE = os.path.dirname(os.path.abspath(__file__))
_CERT = os.path.join(_BASE, "cert.pem")
_KEY = os.path.join(_BASE, "key.pem")

state = AppState(_BASE)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify(state.robot.status_payload())


@app.route("/api/control", methods=["POST"])
def api_control():
    data = request.get_json(silent=True) or {}
    ctrl = state.robot.update_control(data.get("x", 0), data.get("y", 0))
    return jsonify({"status": "ok", **ctrl})


@app.route("/api/io_toggle", methods=["POST"])
def api_io_toggle():
    data = request.get_json(silent=True) or {}
    try:
        index, status = state.robot.toggle_io(data.get("index"))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "index": index, "state": status})


@app.route("/api/io_rename", methods=["POST"])
def api_io_rename():
    data = request.get_json(silent=True) or {}
    try:
        index, name = state.robot.rename_io(data.get("index"), data.get("name", ""))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "index": index, "name": name})


@app.route("/api/rotation", methods=["POST"])
def api_rotation():
    data = request.get_json(silent=True) or {}
    try:
        rotation = state.robot.set_rotation(data.get("rotation"))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "rotation": rotation})


@app.route("/api/update_settings", methods=["POST"])
def api_update_settings():
    data = request.get_json(silent=True) or {}
    payload = state.robot.update_stream_settings(data.get("resolution"), data.get("fps"))
    return jsonify(payload)


# Keep browser requests on one HTTPS origin to avoid mixed-content issues.
def _proxy_mtx(url):
    try:
        req = _urllib_req.Request(
            url,
            data=request.data,
            headers={"Content-Type": "application/sdp"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=12) as response:
            body = response.read()
            return body, response.status, {
                "Content-Type": "application/sdp",
                "Access-Control-Allow-Origin": "*",
            }
    except Exception as exc:
        logging.warning("MTX proxy error (%s): %s", url, exc)
        return str(exc), 502


@app.route("/proxy/whep", methods=["POST"])
def proxy_whep():
    return _proxy_mtx("http://127.0.0.1:8889/robot/whep")


@app.route("/proxy/whip", methods=["POST"])
def proxy_whip():
    return _proxy_mtx("http://127.0.0.1:8889/from-browser/whip")


if __name__ == "__main__":
    ensure_cert(_CERT, _KEY)
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
            "certfile": _CERT,
            "keyfile": _KEY,
            "timeout": 120,
            "keepalive": 2,
            "loglevel": "warning",
            "post_worker_init": lambda worker: state.robot.start_runtime(),
        },
    ).run()
