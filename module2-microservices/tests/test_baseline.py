"""Baseline behaviour - passes on the starter code and must keep passing."""


def test_health(gateway, session):
    r = session.get(f"{gateway}/health")
    assert r.status_code == 200
    up = r.json()["upstream"]
    assert up["device"] == up["reading"] == up["alert"] == "ok"


def test_create_and_get_device(gateway, session):
    r = session.post(f"{gateway}/api/devices", json={"name": "temp-1", "room": "A101", "type": "temperature"})
    assert r.status_code == 201
    dev = r.json()
    assert session.get(f"{gateway}/api/devices/{dev['id']}").json()["room"] == "A101"
    assert any(d["id"] == dev["id"] for d in session.get(f"{gateway}/api/devices").json())


def test_invalid_device_rejected(gateway, session):
    assert session.post(f"{gateway}/api/devices", json={"name": "x"}).status_code == 400
    assert session.post(f"{gateway}/api/devices", json={"name": "x", "room": "r", "type": "pressure"}).status_code == 400


def test_reading_for_unknown_device(gateway, session):
    r = session.post(f"{gateway}/api/readings", json={"device_id": 999999, "value": 20})
    assert r.status_code == 404


def test_reading_creates_alert_when_over_threshold(gateway, session):
    dev = session.post(f"{gateway}/api/devices", json={"name": "co2-1", "room": "B201", "type": "co2"}).json()
    ok = session.post(f"{gateway}/api/readings", json={"device_id": dev["id"], "value": 600})
    assert ok.status_code == 201 and ok.json()["alert"] is None
    hot = session.post(f"{gateway}/api/readings", json={"device_id": dev["id"], "value": 1200})
    assert hot.status_code == 201
    assert hot.json()["alert"]["severity"] == "critical"
    alerts = session.get(f"{gateway}/api/alerts").json()
    assert any(a["device_id"] == dev["id"] for a in alerts)
    readings = session.get(f"{gateway}/api/readings", params={"device_id": dev["id"]}).json()
    assert [r["value"] for r in readings] == [600.0, 1200.0]


def test_unknown_route_is_handled(gateway, session):
    r = session.get(f"{gateway}/api/nothing-here")
    assert r.status_code == 404
    assert "error" in r.json()
