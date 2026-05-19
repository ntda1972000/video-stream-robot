import logging

from interfaces.controller_interface import BaseController

_CMD_MAP = {
    "forward":  b"f",
    "backward": b"b",
    "left":     b"l",
    "right":    b"r",
    "stop":     b"s",
}


class SerialController(BaseController):
    def __init__(self, settings: dict):
        import serial as pyserial
        port     = settings["PORT"]
        baudrate = settings.get("BAUDRATE", 9600)
        self._ser = pyserial.Serial(port, baudrate, timeout=1)
        logging.info("SerialController connected on %s @ %d baud", port, baudrate)

    def _send(self, cmd: bytes) -> None:
        try:
            self._ser.write(cmd)
        except Exception as exc:
            logging.warning("SerialController write error: %s", exc)

    def forward(self) -> None:
        self._send(_CMD_MAP["forward"])

    def backward(self) -> None:
        self._send(_CMD_MAP["backward"])

    def left(self) -> None:
        self._send(_CMD_MAP["left"])

    def right(self) -> None:
        self._send(_CMD_MAP["right"])

    def stop(self) -> None:
        self._send(_CMD_MAP["stop"])

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass
