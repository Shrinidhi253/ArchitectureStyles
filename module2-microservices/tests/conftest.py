import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_all  # noqa: E402

OFFSET = 100
GATEWAY = f"http://127.0.0.1:{5000 + OFFSET}"


@pytest.fixture(scope="session")
def gateway():
    procs = run_all.start(port_offset=OFFSET, reset=True, quiet=True)
    try:
        yield GATEWAY
    finally:
        run_all.stop(procs)


def has_auth(gateway):
    try:
        r = requests.post(f"{gateway}/api/auth/login", json={}, timeout=2)
        return r.status_code != 404
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def session(gateway):
    """A requests session that carries a valid token once Feature 2 exists."""
    s = requests.Session()
    if has_auth(gateway):
        creds = {"username": "tester", "password": "s3cret"}
        requests.post(f"{gateway}/api/auth/register", json=creds, timeout=2)
        token = requests.post(f"{gateway}/api/auth/login", json=creds, timeout=2).json()["token"]
        s.headers["Authorization"] = f"Bearer {token}"
    return s
