import cv2

from interfaces.camera_interface import BaseCamera


class USBCamera(BaseCamera):
    def __init__(self, settings: dict):
        index = settings.get("DEVICE_INDEX", 0)
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open USB camera at index {index}")

    def get_frame(self) -> bytes:
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from USB camera")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Failed to encode frame as JPEG")
        return buf.tobytes()

    def close(self):
        try:
            self._cap.release()
        except Exception:
            pass
