"""Device Service - owns the device registry and ITS OWN database.

Port 5001 (env DEVICE_PORT). No other service may open devices.db.
"""
import os
import sqlite3

from flask import Flask, g, jsonify, request

DB_PATH = os.environ.get("DEVICE_DB", os.path.join(os.path.dirname(__file__), "devices.db"))
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
        db.execute("""CREATE TABLE IF NOT EXISTS devices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        room TEXT NOT NULL,
                        type TEXT NOT NULL CHECK (type IN ('temperature','humidity','co2')))""")


@app.get("/health")
def health():
    return jsonify(service="device", status="ok")


@app.get("/devices")
def list_devices():
    rows = get_db().execute("SELECT * FROM devices ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/devices")
def create_device():
    body = request.get_json(silent=True) or {}
    missing = [k for k in ("name", "room", "type") if not body.get(k)]
    if missing:
        return jsonify(error=f"missing fields: {', '.join(missing)}"), 400
    if body["type"] not in ("temperature", "humidity", "co2"):
        return jsonify(error="type must be temperature, humidity or co2"), 400
    db = get_db()
    cur = db.execute("INSERT INTO devices (name, room, type) VALUES (?, ?, ?)",
                     (body["name"], body["room"], body["type"]))
    db.commit()
    row = db.execute("SELECT * FROM devices WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.get("/devices/<int:device_id>")
def get_device(device_id):
    row = get_db().execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        return jsonify(error="device not found"), 404
    return jsonify(dict(row))


# (Feature 1): DELETE /devices/<id>
@app.delete("/devices/<int:device_id>")
def delete_device(device_id): # the delete request gets routed here
    db = get_db()

    cursor = db.execute("DELETE FROM devices WHERE id = ?;", (device_id,))
    db.commit()

    num_deleted_rows = cursor.rowcount
    if num_deleted_rows == 0: #if no rows are deleted, the device is not found, so return an error message
        return jsonify(error = "device id not found"), 404
    
    return jsonify(deleted = num_deleted_rows), 200 #if the device has been deleted successfully, return the number of deleted row.


@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("DEVICE_PORT", 5001)))
