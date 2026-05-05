import logging
import os
import subprocess


def _collect_non_loopback_ips() -> list[str]:
    try:
        output = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True)
        ips = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != "lo":
                ips.append(parts[3].split("/")[0])
        return ips
    except Exception:
        return []


def ensure_cert(cert_path: str, key_path: str) -> None:
    """Generate a self-signed certificate that includes active host IPs."""
    ips = _collect_non_loopback_ips() or ["127.0.0.1"]
    subject_alt_name = ",".join(f"IP:{ip}" for ip in ips)

    needs_regen = not (os.path.exists(cert_path) and os.path.exists(key_path))

    if not needs_regen:
        try:
            cert_text = subprocess.check_output(["openssl", "x509", "-in", cert_path, "-noout", "-text"], text=True)
            needs_regen = any(ip not in cert_text for ip in ips)
        except Exception:
            needs_regen = True

    if not needs_regen:
        return

    logging.info("Generating self-signed TLS certificate for IPs: %s", ips)
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
            f"subjectAltName={subject_alt_name}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.info("Certificate written: %s", subject_alt_name)
