"""Certificate acquisition utility

Goal: Automatically obtain and cache the TLS server certificate for a non-clarifai.com
Clarifai API base URL so the Clarifai SDK can be given a `root_certificates_path`.

Intended SDK integration pattern (pseudo-code):

    from cert_fetch import get_cert_for_base_url, host_requires_custom_cert

    def configure_client(base_url: str, **auth):
        extra = {}
        if host_requires_custom_cert(base_url):
            cert_path = get_cert_for_base_url(base_url)
            if cert_path:
                extra["root_certificates_path"] = cert_path
        return ClarifaiClient(base_url=base_url, **extra, **auth)

Design notes:
- Uses only the Python standard library.
- Caches certificates on disk under:  ~/.clarifai_certs/<hostname>.pem
- Thread-safe: employs a per-host lock to avoid duplicate fetches.
- Idempotent: reuses existing non-empty PEM file unless `force=True`.
- Conservative timeouts to avoid UI lockups.

Limitations:
- Does not validate certificate chains beyond what the peer presents.
- Does not handle SNI/ALPN edge failures differently (uses default ssl.create_default_context()).
- For deep chain validation, the SDK or environment may incorporate system CAs instead.

"""
from __future__ import annotations

import os
import ssl
import socket
import threading
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

# Global lock map per hostname to prevent concurrent duplicate fetches
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

CERT_DIR_NAME = ".clarifai_certs"
PEM_HEADER = "-----BEGIN CERTIFICATE-----"


def host_requires_custom_cert(base_url: Optional[str]) -> bool:
    """Return True if the base_url host is not a clarifai.com domain.

    Empty or None base_url -> False.
    """
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url if "//" in base_url else f"https://{base_url}")
        host = parsed.hostname or ""
        return bool(host) and not host.endswith("clarifai.com")
    except Exception:
        return True  # Fail closed (treat as custom)


def _cert_storage_dir() -> Path:
    p = Path.home() / CERT_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cert_path_for_host(host: str) -> Path:
    safe = host.replace("/", "_")
    return _cert_storage_dir() / f"{safe}.pem"


def _get_host_lock(host: str) -> threading.Lock:
    with _LOCKS_GUARD:
        if host not in _LOCKS:
            _LOCKS[host] = threading.Lock()
        return _LOCKS[host]


def fetch_and_cache_server_certificate(
    base_url: str,
    *,
    force: bool = False,
    timeout: float = 5.0,
    default_port: int = 443,
) -> Optional[str]:
    """Fetch and cache the server certificate for the given base_url.

    Returns path to PEM, or None on failure / not required.

    Args:
        base_url: The Clarifai (or custom) API base URL.
        force:   If True, re-fetch even if a PEM already exists.
        timeout: Socket timeout for the TLS handshake.
        default_port: Used if URL omits an explicit port.
    """
    if not host_requires_custom_cert(base_url):
        return None

    try:
        parsed = urlparse(base_url if "//" in base_url else f"https://{base_url}")
        host = parsed.hostname
        if not host:
            return None
        port = parsed.port or (default_port if (parsed.scheme or "https").lower().startswith("https") else default_port)
    except Exception:
        return None

    target = _cert_path_for_host(host)

    # Reuse existing file if valid and not forcing
    if not force and target.exists():
        try:
            if target.stat().st_size > 0 and PEM_HEADER in target.read_text(errors="ignore"):
                return str(target)
        except Exception:
            pass

    lock = _get_host_lock(host)
    with lock:
        # Re-check inside lock
        if not force and target.exists():
            try:
                if target.stat().st_size > 0 and PEM_HEADER in target.read_text(errors="ignore"):
                    return str(target)
            except Exception:
                pass

        try:
            pem = ssl.get_server_certificate((host, port))
            if not pem or PEM_HEADER not in pem:
                # Fallback: manual handshake to capture peer cert
                context = ssl.create_default_context()
                with socket.create_connection((host, port), timeout=timeout) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        der = ssock.getpeercert(True)
                        pem = ssl.DER_cert_to_PEM_cert(der)
            if not pem or PEM_HEADER not in pem:
                return None
            target.write_text(pem, encoding="utf-8")
            return str(target)
        except Exception:
            return None


def get_cert_for_base_url(base_url: str) -> Optional[str]:
    """High-level helper: return cert path if required; otherwise None.

    Performs fetch if the file is not cached.
    """
    if not host_requires_custom_cert(base_url):
        return None
    return fetch_and_cache_server_certificate(base_url, force=False)


# Optional environment integration convenience
ENV_CERT_PATH = "CLARIFAI_ROOT_CERTIFICATES_PATH"
ENV_CERT_PATH_ALT = "CLARIFAI_ROOT_CERTS_PATH"


def export_cert_env_if_needed(base_url: str) -> Optional[str]:
    """Fetch certificate (if needed) and set environment variables to its path.

    Returns the path if set, otherwise None.
    """
    cert_path = get_cert_for_base_url(base_url)
    if cert_path:
        os.environ[ENV_CERT_PATH] = cert_path
        os.environ[ENV_CERT_PATH_ALT] = cert_path
    return cert_path


if __name__ == "__main__":  # Simple manual test harness
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cert_fetch.py <base_url> [--force]")
        raise SystemExit(1)
    url = sys.argv[1]
    force_flag = "--force" in sys.argv[2:]
    path = fetch_and_cache_server_certificate(url, force=force_flag)
    if path:
        print(f"Certificate cached at: {path}")
    else:
        print("No certificate fetched (maybe clarifai.com or an error occurred).")
