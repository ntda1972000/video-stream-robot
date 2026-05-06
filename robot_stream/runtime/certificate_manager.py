import logging
import os
import subprocess


def _collect_non_loopback_ips() -> list[str]:
    try:
        out = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True)
        ips = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != "lo":
                ips.append(parts[3].split("/")[0])
        return ips
    except Exception:
        return []


def ensure_cert(cert_path: str, key_path: str) -> None:
    all_ips = _collect_non_loopback_ips()
    if not all_ips:
        all_ips = ["127.0.0.1"]

    san = ",".join(f"IP:{ip}" for ip in all_ips)
    needs_regen = not (os.path.exists(cert_path) and os.path.exists(key_path))

    if not needs_regen:
        try:
            cert_text = subprocess.check_output(
                ["openssl", "x509", "-in", cert_path, "-noout", "-text"], text=True
            )
            needs_regen = any(ip not in cert_text for ip in all_ips)
        except Exception:
            needs_regen = True

    if not needs_regen:
        return

    logging.info("Generating self-signed TLS certificate for IPs: %s", all_ips)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_path,
            "-out",
            cert_path,
            "-days",
            "3650",
            "-nodes",
            "-subj",
            "/CN=robot-pi",
            "-addext",
            f"subjectAltName={san}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.info("Certificate written: %s", san)
