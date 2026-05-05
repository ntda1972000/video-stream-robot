import os
import threading
import time


class NetworkMonitor:
    """Tracks network tx/rx throughput on the preferred interface."""

    def __init__(self):
        self._tx = 0.0
        self._rx = 0.0
        self._pt = 0.0
        self._px = 0.0
        self._py = 0.0
        self._iface = next((name for name in ("wlan0", "wlan1", "eth0") if os.path.exists(f"/sys/class/net/{name}")), None)
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            threading.Thread(target=self._loop, daemon=True, name="network-monitor").start()
            self._started = True

    def _loop(self) -> None:
        while True:
            time.sleep(2)
            if not self._iface:
                continue

            try:
                tx = int(open(f"/sys/class/net/{self._iface}/statistics/tx_bytes", "r", encoding="utf-8").read())
                rx = int(open(f"/sys/class/net/{self._iface}/statistics/rx_bytes", "r", encoding="utf-8").read())
                now = time.time()
                if self._pt > 0 and (now - self._pt) > 0:
                    dt = now - self._pt
                    self._tx = round((tx - self._px) * 8 / (dt * 1000), 1)
                    self._rx = round((rx - self._py) * 8 / (dt * 1000), 1)
                self._pt, self._px, self._py = now, tx, rx
            except Exception:
                pass

    def stats(self) -> dict[str, float | str | None]:
        return {
            "iface": self._iface,
            "tx_kbps": max(0.0, self._tx),
            "rx_kbps": max(0.0, self._rx),
        }
