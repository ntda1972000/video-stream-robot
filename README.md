# video-stream-robot

RC car live stream over WebRTC ? Raspberry Pi camera to browser, over LAN or Tailscale/4G.

## Hardware

- Raspberry Pi 3B+, 4, or 5 (arm64/armv7) or any Linux x86_64 machine
- Raspberry Pi Camera Module (OV5647 or compatible) or USB webcam

## Quick Start

```bash
git clone -b develop https://github.com/ntda1972000/video-stream-robot.git
cd video-stream-robot
chmod +x setup_robot.sh
./setup_robot.sh
```

The setup script will:

1. Install system packages (`ffmpeg`, `python3-venv`, `v4l-utils`, `alsa-utils`, `openssl`, `curl`)
2. Create a Python virtualenv at `.venv` and install **Flask** + **gunicorn**
3. Download **mediamtx v1.9.0** binary to `~/rc-car/mediamtx`
4. _(Optional)_ Install **Tailscale** for remote/4G access
5. _(Optional)_ Install the **systemd service** for autostart on boot

After setup, start the app:

```bash
nohup .venv/bin/python app.py > server.log 2>&1 &
```

Open in a browser and **accept the self-signed certificate**:

```
https://<pi-ip>:5000
```

---

## Remote Access via Tailscale (4G / Internet)

Tailscale creates a private WireGuard mesh, so you can reach the Pi from any device
on the same Tailscale network ? including over 4G with no port forwarding required.

> **Note:** The app uses `webrtcLocalTCPAddress: :8189` so WebRTC automatically falls
> back to TCP when UDP is blocked by the carrier.

### Setup

1. On the Pi, install and authenticate Tailscale:

   ```bash
   # Install (already done if you answered 'y' during setup_robot.sh)
   curl -fsSL https://tailscale.com/install.sh | sh

   # Authenticate (opens a URL ? paste it in any browser)
   sudo tailscale up

   # Get the Pi's Tailscale IP
   tailscale ip -4
   ```

2. On your phone / laptop, install Tailscale and join the **same account**.

3. Open the stream:

   ```
   https://<tailscale-ip>:5000
   ```

### Headless / Unattended Authentication

For deploying to multiple Pis without a browser, use an **auth key**
from <https://login.tailscale.com/admin/settings/keys>:

```bash
sudo tailscale up --authkey=<tskey-auth-...> --hostname=rc-car-pi
```

---

## Autostart on Boot (systemd)

```bash
sudo cp robot-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable robot-stream
sudo systemctl start robot-stream

# Follow logs
journalctl -u robot-stream -f
```

The service waits for `network-online.target` and `tailscaled.service` (if installed)
before starting, so the Tailscale IP is always included in the WebRTC ICE candidates
and the TLS certificate.

---

## Deploying to Multiple Machines

```bash
# On each new Pi (after OS flash and SSH enabled):
git clone -b develop https://github.com/ntda1972000/video-stream-robot.git
cd video-stream-robot
chmod +x setup_robot.sh
./setup_robot.sh

# Authenticate Tailscale with an auth key (no browser needed):
sudo tailscale up --authkey=<tskey-auth-...> --hostname=rc-car-<id>
```

---

## Architecture

```
rpicam-vid ? ffmpeg (H264) ? RTSP :8554/robot
                                        ?
                                    mediamtx
                                        ?
                              WebRTC WHEP :8889
                                        ?
                             Browser ? Flask HTTPS :5000
```

## Ports

| Port | Protocol | Purpose                        |
|------|----------|--------------------------------|
| 5000 | HTTPS    | Flask web UI                   |
| 8554 | RTSP/TCP | Internal camera stream         |
| 8889 | HTTP     | WebRTC WHEP endpoint           |
| 8189 | UDP+TCP  | ICE media (WebRTC)             |
| 9997 | HTTP     | mediamtx REST API (loopback)   |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Browser shows SSL error | Self-signed cert | Click "Advanced ? Proceed" |
| Video never loads (spinning) | ICE failure | Check port 8189 is reachable; TCP fallback handles most cases |
| `mediamtx not found` | Binary missing | Re-run `setup_robot.sh` |
| Black screen, stream "ready" | Camera not detected | Run `v4l2-ctl --list-devices` |
