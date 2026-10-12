"""
Auditing service - owns its own database with the audit_log

Port 5005 (env AUDIT_PORT). No other service may open the audit_log db
"""

import os
import sqlite3

from flask import Flask, g, jsonify, request

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

    rows = db.execute("SELECT * FROM audit_log;").fetchall()
    return jsonify([dict(row) for row in rows]) #return a list of dictionaries of each row in the log

# TODO (Feature 3.2) POST /audit

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("AUDIT_PORT", 5005)))
