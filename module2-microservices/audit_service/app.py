"""
Auditing service - owns its own database with the audit_log

Port 5005 (env AUDIT_PORT). No other service may open the audit_log db
"""

import os
import sqlite3

from flask import Flask, g, jsonify, request
from datetime import datetime, timezone

DB_PATH = os.environ.get("AUDIT_DB", os.path.join(os.path.dirname(__file__), "audit_log.db"))
app = Flask(__name__)

#the below methods follow the other services as a template.
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row

    return g.db

@app.teardown_appcontext
def close_db(_exec):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as db:

        #create a audit_log(log_id, username, timestamp, action, resource, outcome)
        db.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        action TEXT NOT NULL CHECK (action IN ('CREATE', 'DELETE', 'RETRIEVE')),
                        resource TEXT NOT NULL,
                        outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'error')),
                        detail TEXT
                  );""")
        

@app.get("/health")
def health():
    return jsonify(service = "audit", status = "ok")

# (Feature 3.1) GET /audit
@app.get("/audit")
def get_audit_log():
    db = get_db()

    rows = db.execute("SELECT * FROM audit_log ORDER BY log_id;").fetchall() #the output is sorted in the insertion order
    return jsonify([dict(row) for row in rows]) #return a list of dictionaries of each row in the log

# (Feature 3.2) POST /audit
@app.post("/audit")
def add_log_entry(): #record an entry in the log
    body = request.get_json(silent = True) or {}

    missing_fields = [field for field in ("username", "action", "resource", "outcome") if not body.get(field)]
    if missing_fields:
        return jsonify(error = f"Missing fields: {', '.join(missing_fields)}. Could not add log entry."), 400
    
    #check if provided action and outcome values are valid.
    if body["action"] not in ("CREATE", "DELETE", "RETRIEVE"):
        return jsonify(error = "action must be CREATE, DELETE, or RETRIEVE"), 400
        
    if body["outcome"] not in ("ok", "error"):
        return jsonify(error = "outcome must be ok, or error"), 400
    
    db = get_db()

    #if timestamp is provided use that, or use the current time as the timestamp
    timestamp = body["timestamp"] or datetime.now(timezone.utc).isoformat(timespec="seconds")

    cursor = db.execute("INSERT INTO audit_log(username, timestamp, action, resource, outcome, detail) VALUES (?, ?, ?, ?, ?, ?);",
                   (body["username"], timestamp, body["action"], body["resource"], body["outcome"], body.get("detail"))
                )
    
    db.commit()

    #get the added row for success message
    added_row = db.execute("SELECT * FROM audit_log WHERE log_id = ?;", (cursor.lastrowid,))
    
    return jsonify(dict(added_row)), 201

#Handling every other error
@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("AUDIT_PORT", 5005)))
