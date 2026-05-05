import logging
import os
import urllib.request as urllib_request

from flask import Flask, jsonify, render_template, request

from robot_stream.app_context import AppContext
from robot_stream.errors import ValidationError
from robot_stream.runtime.certificate_manager import ensure_cert


def create_app(project_root: str) -> tuple[Flask, AppContext, str, str]:
    """Create Flask app and dependency context for the robot stream server."""
    app = Flask(__name__, template_folder=os.path.join(project_root, "templates"))
    context = AppContext(project_root)
    cert_path = os.path.join(project_root, "cert.pem")
    key_path = os.path.join(project_root, "key.pem")

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/api/status")
    def api_status():
        return jsonify(context.robot.status_payload())

    @app.route("/api/control", methods=["POST"])
    def api_control():
        payload = request.get_json(silent=True) or {}
        control_state = context.robot.update_control(payload.get("x", 0), payload.get("y", 0))
        return jsonify({"status": "ok", **control_state})

    @app.route("/api/io_toggle", methods=["POST"])
    def api_io_toggle():
        payload = request.get_json(silent=True) or {}
        try:
            index, state = context.robot.toggle_io(payload.get("index"))
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "index": index, "state": state})

    @app.route("/api/io_rename", methods=["POST"])
    def api_io_rename():
        payload = request.get_json(silent=True) or {}
        try:
            index, name = context.robot.rename_io(payload.get("index"), payload.get("name", ""))
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "index": index, "name": name})

    @app.route("/api/rotation", methods=["POST"])
    def api_rotation():
        payload = request.get_json(silent=True) or {}
        try:
            rotation = context.robot.set_rotation(payload.get("rotation"))
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "rotation": rotation})

    @app.route("/api/update_settings", methods=["POST"])
    def api_update_settings():
        payload = request.get_json(silent=True) or {}
        return jsonify(context.robot.update_stream_settings(payload.get("resolution"), payload.get("fps")))

    def proxy_to_mediamtx(url: str):
        try:
            upstream_request = urllib_request.Request(
                url,
                data=request.data,
                headers={"Content-Type": "application/sdp"},
                method="POST",
            )
            with urllib_request.urlopen(upstream_request, timeout=12) as upstream_response:
                body = upstream_response.read()
                return body, upstream_response.status, {
                    "Content-Type": "application/sdp",
                    "Access-Control-Allow-Origin": "*",
                }
        except Exception as exc:
            logging.warning("MTX proxy error (%s): %s", url, exc)
            return str(exc), 502

    @app.route("/proxy/whep", methods=["POST"])
    def proxy_whep():
        return proxy_to_mediamtx("http://127.0.0.1:8889/robot/whep")

    @app.route("/proxy/whip", methods=["POST"])
    def proxy_whip():
        return proxy_to_mediamtx("http://127.0.0.1:8889/from-browser/whip")

    app.extensions["app_context"] = context
    return app, context, cert_path, key_path


def run_server(project_root: str) -> None:
    """Run HTTPS gunicorn server with robot runtime lifecycle hooks."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    app, context, cert_path, key_path = create_app(project_root)
    ensure_cert(cert_path, key_path)

    logging.info("Starting HTTPS on port 5000 via gunicorn")

    import gunicorn.app.base

    class GunicornApp(gunicorn.app.base.BaseApplication):
        def __init__(self, application, options=None):
            self.options = options or {}
            self.application = application
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    GunicornApp(
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
            "post_worker_init": lambda worker: context.robot.start_runtime(),
        },
    ).run()
