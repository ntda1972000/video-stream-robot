import io

from interfaces.camera_interface import BaseCamera


class PiCamera(BaseCamera):
    def __init__(self, settings: dict):
        from picamera2 import Picamera2
        resolution = settings.get("RESOLUTION", (640, 480))
        self._cam = Picamera2()
        config = self._cam.create_still_configuration(
            main={"size": tuple(resolution), "format": "RGB888"}
        )
        self._cam.configure(config)
        self._cam.start()

    def get_frame(self) -> bytes:
        buf = io.BytesIO()
        self._cam.capture_file(buf, format="jpeg")
        return buf.getvalue()

    def close(self):
        try:
            self._cam.stop()
        except Exception:
            pass
