import re
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # tillåt anrop från din frontend (Lovable/Netlify/etc)

DB_PATH = Path(__file__).parent / "incident_tracker.db"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            kommun TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


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
    try:
        conn.execute(
            "INSERT INTO users (name, email, kommun) VALUES (?, ?, ?)",
            (name, email, kommun),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "E-postadressen är redan registrerad."}), 409
    finally:
        conn.close()

    return jsonify({"ok": True}), 201


@app.get("/api/users")
def list_users():
    # Läses av send_email.py. Lägg till en delad hemlighet (header/token)
    # innan du hostar detta publikt, annars kan vem som helst dumpa listan.
    conn = get_db()
    rows = conn.execute("SELECT name, email, kommun FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.delete("/api/users/<email>")
def delete_user(email):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE email = ?", (email.lower(),))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


init_db()

...

if __name__ == "__main__":
    app.run(debug=True, port=5000)
