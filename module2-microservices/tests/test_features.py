"""Feature tests for Module 2, Part 1. Expected to FAIL on the starter code."""
import requests

from .conftest import OFFSET, has_auth


# ---------------------------------------------------------------- Feature 1
def test_delete_device_removes_device_and_its_readings(gateway, session):
    dev = session.post(f"{gateway}/api/devices", json={"name": "del-1", "room": "C1", "type": "humidity"}).json()
    session.post(f"{gateway}/api/readings", json={"device_id": dev["id"], "value": 50})
    session.post(f"{gateway}/api/readings", json={"device_id": dev["id"], "value": 55})
    assert len(session.get(f"{gateway}/api/readings", params={"device_id": dev["id"]}).json()) == 2

    r = session.delete(f"{gateway}/api/devices/{dev['id']}")
    assert r.status_code in (200, 204)
    assert session.get(f"{gateway}/api/devices/{dev['id']}").status_code == 404
    assert session.get(f"{gateway}/api/readings", params={"device_id": dev["id"]}).json() == []


def test_delete_unknown_device_is_404_not_crash(gateway, session):
    r = session.delete(f"{gateway}/api/devices/987654")
    assert r.status_code == 404
    assert "error" in r.json()
    # the system is still alive afterwards
    assert session.get(f"{gateway}/health").status_code == 200


def test_delete_with_invalid_id_is_handled(gateway, session):
    r = session.delete(f"{gateway}/api/devices/not-a-number")
    assert r.status_code in (400, 404)


# ---------------------------------------------------------------- Feature 2
def test_auth_endpoints_exist(gateway):
    assert has_auth(gateway), "POST /api/auth/login must exist"


def test_register_login_and_token_required(gateway):
    creds = {"username": "alice", "password": "wonderland"}
    r = requests.post(f"{gateway}/api/auth/register", json=creds)
    assert r.status_code == 201
    assert requests.post(f"{gateway}/api/auth/register", json=creds).status_code == 409  # duplicate

    bad = requests.post(f"{gateway}/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401
    good = requests.post(f"{gateway}/api/auth/login", json=creds)
    assert good.status_code == 200 and good.json()["token"]

    # without a token the domain APIs are closed ...
    assert requests.get(f"{gateway}/api/devices").status_code == 401
    assert requests.post(f"{gateway}/api/devices", json={"name": "n", "room": "r", "type": "co2"}).status_code == 401
    assert requests.get(f"{gateway}/api/devices", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    # ... with a token they are open
    ok = requests.get(f"{gateway}/api/devices", headers={"Authorization": f"Bearer {good.json()['token']}"})
    assert ok.status_code == 200


def test_domain_services_do_not_know_about_users(gateway, session):
    """Auth is a gateway concern: the device service itself must not require a token."""
    device_url = f"http://127.0.0.1:{5001 + OFFSET}"
    assert requests.get(f"{device_url}/devices").status_code == 200


# ---------------------------------------------------------------- Feature 3
def test_actions_are_audited_with_username(gateway, session):
    dev = session.post(f"{gateway}/api/devices", json={"name": "aud-1", "room": "D1", "type": "co2"}).json()
    session.get(f"{gateway}/api/devices/{dev['id']}")
    session.delete(f"{gateway}/api/devices/{dev['id']}")
    entries = session.get(f"{gateway}/api/audit").json()
    mine = [e for e in entries if e.get("username") == "tester" and str(dev["id"]) in e.get("resource", "")]
    actions = [e["action"] for e in mine]
    assert "RETRIEVE" in actions and "DELETE" in actions
    creates = [e for e in entries if e.get("username") == "tester" and e["action"] == "CREATE"]
    assert creates, "CREATE actions must be audited"
    for e in mine:
        assert e["ts"] and e["outcome"] in ("ok", "error")


def test_failures_are_audited(gateway, session):
    session.get(f"{gateway}/api/devices/424242")          # 404 from the device service
    entries = session.get(f"{gateway}/api/audit").json()
    errors = [e for e in entries if e["outcome"] == "error" and "424242" in e.get("resource", "")]
    assert errors and errors[-1]["action"] == "RETRIEVE"
    assert errors[-1]["detail"]
