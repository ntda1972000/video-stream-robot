import os
import subprocess
import threading
import time


class NetworkMonitor:
    def __init__(self):
        self._tx = self._rx = 0.0
        self._pt = self._px = self._py = 0.0
        self._iface = self._pick_iface()
        threading.Thread(target=self._loop, daemon=True).start()

    @staticmethod
    def _pick_iface():
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            for line in out.splitlines():
                parts = line.split()
                if "dev" in parts:
                    dev = parts[parts.index("dev") + 1]
                    if os.path.exists(f"/sys/class/net/{dev}/statistics/tx_bytes"):
                        return dev
        except Exception:
            pass

        try:
            best, best_tx = None, -1
            for name in os.listdir("/sys/class/net"):
                if name == "lo":
                    continue
                try:
                    with open(f"/sys/class/net/{name}/statistics/tx_bytes") as handle:
                        tx = int(handle.read())
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
            if not self._iface:
                continue
            try:
                with open(f"/sys/class/net/{self._iface}/statistics/tx_bytes") as handle:
                    tx = int(handle.read())
                with open(f"/sys/class/net/{self._iface}/statistics/rx_bytes") as handle:
                    rx = int(handle.read())
                now = time.time()
                if self._pt > 0 and (now - self._pt) > 0:
                    dt = now - self._pt
                    self._tx = round((tx - self._px) * 8 / (dt * 1000), 1)
                    self._rx = round((rx - self._py) * 8 / (dt * 1000), 1)
                self._pt, self._px, self._py = now, tx, rx
            except Exception:
                pass

    def stats(self):
        return {
            "iface": self._iface,
            "tx_kbps": max(0.0, self._tx),
            "rx_kbps": max(0.0, self._rx),
        }
