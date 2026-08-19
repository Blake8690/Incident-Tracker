import os
import re

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ["DATABASE_URL"]
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            kommun TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS skickade_handelser (
            event_id TEXT PRIMARY KEY,
            skickad_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


init_db()


@app.post("/api/users")
def register_user():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    kommun = (data.get("kommun") or "").strip()

    if not name or len(name) > 100:
        return jsonify({"error": "Ogiltigt namn."}), 400
    if not EMAIL_RE.match(email) or len(email) > 255:
        return jsonify({"error": "Ogiltig e-postadress."}), 400
    if not kommun:
        return jsonify({"error": "Kommun krävs."}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, kommun) VALUES (%s, %s, %s)",
            (name, email, kommun),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "E-postadressen är redan registrerad."}), 409
    finally:
        cur.close()
        conn.close()

    return jsonify({"ok": True}), 201


@app.get("/api/users")
def list_users():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name, email, kommun FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.delete("/api/users/<email>")
def delete_user(email):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email = %s", (email.lower(),))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


@app.get("/api/skickade")
def get_skickade():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT event_id FROM skickade_handelser")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([r[0] for r in rows])


@app.post("/api/skickade")
def add_skickad():
    data = request.get_json(silent=True) or {}
    event_id = str(data.get("event_id", "")).strip()
    if not event_id:
        return jsonify({"error": "event_id krävs"}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO skickade_handelser (event_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (event_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)