"""
Authentication service - owns its own database with users and their tokens

Port 5004 (env AUTH_PORT). No other service may open auth db
"""

import os
import sqlite3

from flask import Flask, g, jsonify, request
import secrets

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

# (Feature 2.2) POST /login
@app.post("/login")
def login_user():
    body = request.get_json(silent = True) or {}

    # check for missing fields as before
    missing_fields = [field for field in ("username", "password") if not body.get(field)]

    if missing_fields:
        return jsonify(error = f"Missing fields: {','.join(missing_fields)}"), 400


    username, password = body.get("username"), body.get("password")
    db = get_db()

    user_row = db.execute("SELECT * FROM users WHERE users.username = ?;", (username,)).fetchone()

    # check for invalid username and password
    if user_row is None or user_row["password"] != password: 
        return jsonify(error = "Invalid username or password"), 401
    

    # create a token for the user
    token = secrets.token_urlsafe(32) #32 bit token

    db.execute("INSERT INTO tokens(token, user_id) VALUES (?, ?);", (token, user_row["user_id"]))
    db.commit()
    
    return jsonify(token = token), 200

@app.get("/validate")
def validate_session(): #checks if the token is valid
    auth_header = request.headers.get("Authorization", "") #the token is passed in the headers

    if not auth_header.startswith("Bearer "): #The header is of the format Authorization: Bearer <credential>
        return jsonify(error = "missing or malformed authorization header"), 401
    
    token = auth_header[len("Bearer"):].strip() #only slice the token credentials

    #check if the token exists in the database. if the token exists, return the username of the user
    db = get_db()
    row = db.execute("""SELECT users.username FROM tokens
                        JOIN users ON users.user_id = tokens.user_id
                        WHERE tokens.token = ?;
                    """, (token,)).fetchone()
    
    if row is None: #if token row couldn't be found, return invalid token error
        return jsonify(error = "invalid token"), 401
    
    return jsonify(username = row["username"]), 200

#error handling block similar to other services
@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("AUTH_PORT", 5004)))