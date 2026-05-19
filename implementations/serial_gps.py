import logging

import pynmea2

from interfaces.gps_interface import BaseGPS


class SerialGPS(BaseGPS):
    def __init__(self, settings: dict):
        import serial as pyserial
        port     = settings["PORT"]
        baudrate = settings.get("BAUDRATE", 9600)
        self._ser = pyserial.Serial(port, baudrate, timeout=1)
        logging.info("SerialGPS connected on %s @ %d baud", port, baudrate)

    def get_coordinates(self) -> tuple[float, float] | None:
        """Read up to 20 NMEA lines and return (latitude, longitude) on first fix."""
        for _ in range(20):
            try:
                raw = self._ser.readline()
                line = raw.decode("ascii", errors="ignore").strip()
                if not line.startswith("$"):
                    continue
                msg = pynmea2.parse(line)
                if hasattr(msg, "latitude") and msg.latitude:
                    return (msg.latitude, msg.longitude)
            except pynmea2.ParseError:
                continue
            except Exception as exc:
                logging.warning("SerialGPS read error: %s", exc)
                break
        return None

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass
