"""
Authentication service - owns its own database with users and their tokens

Port 5004 (env AUTH_PORT). No other service may open auth db
"""

import os
import sqlite3

from flask import Flask, g, jsonify, request

DB_PATH = os.environ.get("AUTH_DB", os.path.join(os.path.dirname(__file__), "auth.db"))
app = Flask(__name__)

# the below methods follow the device_service/app.py as a template.
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

        # create a users(user_id, username, password) table in the database
        db.execute("""CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL
                   );""")
        
        # create a tokens(token, user_id) table in the database
        # the tokens table is created separately from the users because a user may choose to have mutliple tokens.
        # the user_id is a foreign key to the users db
        db.execute("""CREATE TABLE IF NOT EXISTS tokens (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(user_id)
                   );""")
        
@app.get("/health")
def health():
    return jsonify(service = "auth", status = "ok")

# (Feature 2.1) POST /register
@app.post("/register")
def register_user():
    body = request.get_json(silent = True) or {}

    # return an error with the fields missing in the body of the request (if any)
    missing_fields = [field for field in ("username", "password") if not body.get(field)]

    if missing_fields:
        return jsonify(error = f"Missing fields: {','.join(missing_fields)}"), 400
    
    # Add the username and the password to the database and return the user's user id
    db = get_db()
    username, password = body.get("username"), body.get("password")
    
    try:
        cursor = db.execute("INSERT INTO users(username, password) VALUES (?, ?);", (username, password))
        db.commit()
    
    except sqlite3.IntegrityError: # if this exception occurs during the insert, it is because the UNIQUE check for the username field failed, i.e. username exists
        return jsonify(error = "Username already exists"), 409
    
    return jsonify(user_id = cursor.lastrowid), 201

# TODO (Feature 2.2) POST /api/auth/login