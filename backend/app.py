import hmac
import os
import re
import secrets

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ["DATABASE_URL"]
# Delad hemlighet mellan backend och GitHub Action (send_email.py).
# Skyddar endpoints som exponerar e-postadresser.
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):(00|30)$")
DELIVERY_MODES = ("live", "digest")


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
    # Nya kolumner. Befintliga användare behåller live-utskick och får
    # inget välkomstmejl (welcome_sent backfylls till TRUE).
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS delivery_mode TEXT NOT NULL DEFAULT 'live'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS digest_time TEXT NOT NULL DEFAULT '21:00'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS manage_token TEXT UNIQUE")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_digest_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_sent BOOLEAN NOT NULL DEFAULT TRUE")
    cur.execute("ALTER TABLE users ALTER COLUMN welcome_sent SET DEFAULT FALSE")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS manage_requested BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS manage_sent_at TIMESTAMPTZ")

    cur.execute("SELECT id FROM users WHERE manage_token IS NULL")
    for (user_id,) in cur.fetchall():
        cur.execute(
            "UPDATE users SET manage_token = %s WHERE id = %s",
            (secrets.token_urlsafe(24), user_id),
        )

    # Gammal global logg över skickade händelser. Läses fortfarande så att
    # live-användare inte får om händelser som skickades före bytet.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS skickade_handelser (
            event_id TEXT PRIMARY KEY,
            skickad_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Per användare, eftersom live och sammanfattning skickas vid olika tider.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_events (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL,
            sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, event_id)
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


init_db()


def require_worker():
    if not WORKER_TOKEN:
        return jsonify({"error": "WORKER_TOKEN saknas på servern."}), 503
    given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given, WORKER_TOKEN):
        return jsonify({"error": "Obehörig."}), 401
    return None


def parse_delivery(data, defaults):
    """Validerar delivery_mode/digest_time. Returnerar (mode, time, fel)."""
    mode = (data.get("delivery_mode") or defaults[0]).strip()
    digest_time = (data.get("digest_time") or defaults[1]).strip()
    if mode not in DELIVERY_MODES:
        return None, None, "Ogiltigt leveranssätt."
    if not TIME_RE.match(digest_time):
        return None, None, "Ogiltig tid."
    return mode, digest_time, None


@app.get("/")
def health():
    return jsonify({"ok": True})


@app.post("/api/users")
def register_user():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    kommun = (data.get("kommun") or "").strip()
    mode, digest_time, err = parse_delivery(data, ("live", "21:00"))

    if not name or len(name) > 100:
        return jsonify({"error": "Ogiltigt namn."}), 400
    if not EMAIL_RE.match(email) or len(email) > 255:
        return jsonify({"error": "Ogiltig e-postadress."}), 400
    if not kommun or len(kommun) > 60:
        return jsonify({"error": "Kommun krävs."}), 400
    if err:
        return jsonify({"error": err}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (name, email, kommun, delivery_mode, digest_time, manage_token, last_digest_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (name, email, kommun, mode, digest_time, secrets.token_urlsafe(24)),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "E-postadressen är redan registrerad."}), 409
    finally:
        cur.close()
        conn.close()

    return jsonify({"ok": True}), 201


# ---------- Hantera prenumeration (via hemlig länk i varje mejl) ----------

@app.post("/api/manage-link")
def request_manage_link():
    """Ber workern mejla en hanteringslänk. Svarar alltid likadant så att
    man inte kan ta reda på vilka adresser som är registrerade."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if EMAIL_RE.match(email):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET manage_requested = TRUE WHERE email = %s", (email,))
        conn.commit()
        cur.close()
        conn.close()
    return jsonify({"ok": True})


def find_by_token(cur, token):
    cur.execute(
        "SELECT id, name, email, kommun, delivery_mode, digest_time FROM users WHERE manage_token = %s",
        (token,),
    )
    return cur.fetchone()


@app.get("/api/subscription/<token>")
def get_subscription(token):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    row = find_by_token(cur, token)
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "Länken är ogiltig eller prenumerationen avslutad."}), 404
    row.pop("id")
    return jsonify(row)


@app.patch("/api/subscription/<token>")
def update_subscription(token):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    row = find_by_token(cur, token)
    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "Länken är ogiltig eller prenumerationen avslutad."}), 404

    kommun = (data.get("kommun") or row["kommun"]).strip()
    mode, digest_time, err = parse_delivery(data, (row["delivery_mode"], row["digest_time"]))
    if err or not kommun or len(kommun) > 60:
        cur.close()
        conn.close()
        return jsonify({"error": err or "Kommun krävs."}), 400

    # Byter man till sammanfattning räknas fönstret från nu, så att man inte
    # direkt får ett mejl med händelser man redan fått live.
    cur.execute(
        """
        UPDATE users SET kommun = %s, delivery_mode = %s, digest_time = %s,
            last_digest_at = CASE WHEN delivery_mode <> %s THEN NOW() ELSE last_digest_at END
        WHERE id = %s
        """,
        (kommun, mode, digest_time, mode, row["id"]),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


@app.delete("/api/subscription/<token>")
def delete_subscription(token):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE manage_token = %s", (token,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        return jsonify({"error": "Prenumerationen finns inte."}), 404
    return jsonify({"ok": True})


# ---------- Endpoints för send_email.py (kräver WORKER_TOKEN) ----------

@app.get("/api/worker/users")
def worker_users():
    denied = require_worker()
    if denied:
        return denied
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT u.id, u.name, u.email, u.kommun, u.delivery_mode, u.digest_time,
               u.manage_token, u.created_at, u.last_digest_at, u.welcome_sent,
               u.manage_requested, u.manage_sent_at,
               COALESCE(
                   ARRAY_AGG(e.event_id) FILTER (WHERE e.event_id IS NOT NULL), '{}'
               ) AS sent_ids
        FROM users u
        LEFT JOIN user_events e
               ON e.user_id = u.id AND e.sent_at > NOW() - INTERVAL '3 days'
        GROUP BY u.id
        """
    )
    users = cur.fetchall()
    cur.execute("SELECT event_id FROM skickade_handelser WHERE skickad_at > NOW() - INTERVAL '3 days'")
    legacy = [r["event_id"] for r in cur.fetchall()]
    cur.close()
    conn.close()

    for u in users:
        for key in ("created_at", "last_digest_at", "manage_sent_at"):
            u[key] = u[key].isoformat() if u[key] else None
    return jsonify({"users": users, "legacy_sent": legacy})


@app.post("/api/worker/report")
def worker_report():
    """Tar emot vad workern har skickat:
    {"sent": [{"user_id": 1, "event_ids": ["..."]}], "digested": [ids],
     "welcomed": [ids], "manage_sent": [ids]}"""
    denied = require_worker()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}

    def ids(key):
        return [int(x) for x in data.get(key, []) if str(x).isdigit()]

    rows = [
        (int(s["user_id"]), str(eid))
        for s in data.get("sent", [])
        for eid in s.get("event_ids", [])
    ]
    conn = get_db()
    cur = conn.cursor()
    if rows:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO user_events (user_id, event_id) VALUES %s ON CONFLICT DO NOTHING",
            rows,
        )
    if ids("digested"):
        cur.execute("UPDATE users SET last_digest_at = NOW() WHERE id = ANY(%s)", (ids("digested"),))
    if ids("welcomed"):
        cur.execute("UPDATE users SET welcome_sent = TRUE WHERE id = ANY(%s)", (ids("welcomed"),))
    if ids("manage_sent"):
        cur.execute(
            "UPDATE users SET manage_requested = FALSE, manage_sent_at = NOW() WHERE id = ANY(%s)",
            (ids("manage_sent"),),
        )
    # Städa bort gamla rader så tabellen inte växer i all evighet
    cur.execute("DELETE FROM user_events WHERE sent_at < NOW() - INTERVAL '7 days'")
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)