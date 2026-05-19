import cv2

from interfaces.camera_interface import BaseCamera


class IPCamera(BaseCamera):
    def __init__(self, settings: dict):
        url = settings["RTSP_URL"]
        self._cap = cv2.VideoCapture(url)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open RTSP stream: {url}")

    def get_frame(self) -> bytes:
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from IP camera")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Failed to encode frame as JPEG")
        return buf.tobytes()

    def close(self):
        try:
            self._cap.release()
        except Exception:
            pass
