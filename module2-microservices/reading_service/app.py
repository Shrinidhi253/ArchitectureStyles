"""Reading Service - stores sensor readings in ITS OWN database.

Port 5002 (env READING_PORT). Talks to the Device Service and the Alert
Service only through their HTTP APIs (never through their databases).
"""
import os
import sqlite3
from datetime import datetime, timezone

import requests
from flask import Flask, g, jsonify, request

DB_PATH = os.environ.get("READING_DB", os.path.join(os.path.dirname(__file__), "readings.db"))
DEVICE_URL = os.environ.get("DEVICE_URL", "http://127.0.0.1:5001")
ALERT_URL = os.environ.get("ALERT_URL", "http://127.0.0.1:5003")
app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id INTEGER NOT NULL,
                        ts TEXT NOT NULL,
                        type TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT NOT NULL)""")


@app.get("/health")
def health():
    return jsonify(service="reading", status="ok")


@app.get("/readings")
def list_readings():
    device_id = request.args.get("device_id", type=int)
    db = get_db()
    if device_id is None:
        rows = db.execute("SELECT * FROM readings ORDER BY id").fetchall()
    else:
        rows = db.execute("SELECT * FROM readings WHERE device_id = ? ORDER BY id", (device_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/readings")
def create_reading():
    body = request.get_json(silent=True) or {}
    try:
        device_id = int(body["device_id"])
        value = float(body["value"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="device_id (int) and value (number) are required"), 400

    # Ask the Device Service whether the device exists (synchronous call).
    try:
        resp = requests.get(f"{DEVICE_URL}/devices/{device_id}", timeout=2)
    except requests.RequestException as exc:
        return jsonify(error="device service unavailable", detail=str(exc)), 503
    if resp.status_code == 404:
        return jsonify(error=f"device {device_id} does not exist"), 404
    if resp.status_code != 200:
        return jsonify(error="device service error"), 502
    device = resp.json()

    ts = body.get("ts") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    unit = body.get("unit") or {"temperature": "C", "humidity": "%", "co2": "ppm"}[device["type"]]
    db = get_db()
    cur = db.execute("INSERT INTO readings (device_id, ts, type, value, unit) VALUES (?, ?, ?, ?, ?)",
                     (device_id, ts, device["type"], value, unit))
    db.commit()
    reading = dict(db.execute("SELECT * FROM readings WHERE id = ?", (cur.lastrowid,)).fetchone())

    # Let the Alert Service evaluate the reading (synchronous call, best effort).
    alert = None
    try:
        r = requests.post(f"{ALERT_URL}/alerts/evaluate",
                          json={"device_id": device_id, "room": device["room"], "type": device["type"],
                                "value": value, "ts": ts}, timeout=2)
        if r.status_code == 201:
            alert = r.json()
    except requests.RequestException as exc:
        app.logger.warning("alert service unavailable: %s", exc)
    return jsonify(reading=reading, alert=alert), 201


# (Feature 1): DELETE /readings?device_id=<id>  (needed so a device delete can
#              remove its readings WITHOUT the device service touching readings.db)
@app.delete("/readings")
def delete_readings():
    #Given that the DELETE request has argument device_id=<id>, So get the value of the device_id from the request arg
    device_id = request.args.get("device_id", type = int)

    if device_id is None:
        return jsonify(error="device_id (int) is required"), 400
    
    #if a device_is given in the request, delete the rows for that device in the readings db
    db = get_db()
    cursor = db.execute("DELETE FROM readings WHERE device_id = ?;", (device_id,))
    db.commit()

    return jsonify(deleted = cursor.rowcount), 200 #return the number of rows deleted as a part success message.





@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("READING_PORT", 5002)))
