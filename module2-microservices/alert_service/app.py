"""Alert Service - evaluates readings against thresholds and stores alerts
in ITS OWN database. Port 5003 (env ALERT_PORT).
"""
import os
import sqlite3

from flask import Flask, g, jsonify, request

DB_PATH = os.environ.get("ALERT_DB", os.path.join(os.path.dirname(__file__), "alerts.db"))
THRESHOLDS = {"temperature": 26.0, "humidity": 70.0, "co2": 1000.0}
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
        db.execute("""CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id INTEGER NOT NULL,
                        room TEXT NOT NULL,
                        type TEXT NOT NULL,
                        value REAL NOT NULL,
                        threshold REAL NOT NULL,
                        severity TEXT NOT NULL,
                        ts TEXT NOT NULL)""")


@app.get("/health")
def health():
    return jsonify(service="alert", status="ok")


@app.get("/alerts")
def list_alerts():
    rows = get_db().execute("SELECT * FROM alerts ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/alerts/evaluate")
def evaluate():
    body = request.get_json(silent=True) or {}
    try:
        rtype, value = body["type"], float(body["value"])
        threshold = THRESHOLDS[rtype]
    except (KeyError, TypeError, ValueError):
        return jsonify(error="type (known) and value (number) are required"), 400
    if value <= threshold:
        return jsonify(alert=None), 200
    severity = "critical" if value > threshold * 1.10 else "warning"
    db = get_db()
    cur = db.execute("INSERT INTO alerts (device_id, room, type, value, threshold, severity, ts) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (body.get("device_id"), body.get("room", "?"), rtype, value, threshold, severity,
                      body.get("ts", "")))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM alerts WHERE id = ?", (cur.lastrowid,)).fetchone())), 201


@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("ALERT_PORT", 5003)))
