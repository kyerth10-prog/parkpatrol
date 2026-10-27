"""MySQL storage for Park Patrol.

Writes go through a single background worker so a slow or offline database
never delays the tracker or the dashboard. If MySQL is unreachable the server
keeps running from memory and retries the connection.
"""
import os
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import pymysql

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "database" / "schema.sql"

HOST = os.environ.get("DB_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("DB_PORT", "3306"))
USER = os.environ.get("DB_USER", "root").strip()
PASSWORD = os.environ.get("DB_PASSWORD", "")
NAME = os.environ.get("DB_NAME", "parkpatrol").strip()
ENABLED = os.environ.get("DB_ENABLED", "true").lower() != "false"

RETRY_SECONDS = 15

_jobs = queue.Queue(maxsize=10_000)
_conn = None
_last_failure = 0.0
_warned = False
_violation_ids = {}
_admin_ids = {}


# ----------------------------------------------------------------------------
# Connection
# ----------------------------------------------------------------------------
def _dt(ts):
    return datetime.fromtimestamp(ts) if ts is not None else None


def _connect(database=NAME):
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, database=database,
        charset="utf8mb4", autocommit=True, connect_timeout=5,
    )


def _connection():
    global _conn, _last_failure, _warned
    if _conn is not None:
        try:
            _conn.ping(reconnect=True)
            return _conn
        except pymysql.MySQLError:
            _conn = None
    if time.time() - _last_failure < RETRY_SECONDS:
        return None
    try:
        _conn = _connect()
        if _warned:
            print("Database: reconnected to MySQL")
        _warned = False
        return _conn
    except pymysql.MySQLError as error:
        _last_failure = time.time()
        if not _warned:
            print(f"Database: MySQL unavailable ({error}); running without saving history")
            _warned = True
        return None


def _create_schema():
    """Create the database and tables if they don't exist yet."""
    sql = SCHEMA_FILE.read_text()
    sql = re.sub(r"--[^\n]*", "", sql)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    conn = _connect(database=None)
    try:
        with conn.cursor() as cur:
            for statement in statements:
                if statement.upper().startswith("USE "):
                    cur.execute(f"USE `{NAME}`")
                elif statement.upper().startswith("CREATE DATABASE"):
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{NAME}` "
                                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                else:
                    cur.execute(statement)
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Worker
# ----------------------------------------------------------------------------
def _worker():
    while True:
        job = _jobs.get()
        conn = _connection()
        if conn is None:
            continue
        try:
            with conn.cursor() as cur:
                job(cur)
        except Exception as error:
            print("Database error:", error)


def _submit(job):
    if not ENABLED:
        return
    try:
        _jobs.put_nowait(job)
    except queue.Full:
        pass


def start():
    """Create tables, start the writer thread, and return saved spot states."""
    if not ENABLED:
        return {}
    try:
        _create_schema()
    except pymysql.MySQLError as error:
        print(f"Database: could not prepare MySQL ({error}); running without saving history")
    threading.Thread(target=_worker, daemon=True, name="database").start()
    return load_spots()


def load_spots():
    conn = _connection()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, status_since FROM spots")
            return {row[0]: (row[1], row[2].timestamp()) for row in cur.fetchall()}
    except pymysql.MySQLError as error:
        print("Database error:", error)
        return {}


# ----------------------------------------------------------------------------
# Admins and sign-in
# ----------------------------------------------------------------------------
def admin_login(user, ip, user_agent):
    now = datetime.now()
    sub, email = user.get("sub"), (user.get("email") or "").lower()

    def job(cur):
        cur.execute(
            """INSERT INTO admins (google_sub, email, name, given_name, family_name, picture_url,
                                   hosted_domain, locale, login_count, first_login, last_login)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
               ON DUPLICATE KEY UPDATE email = VALUES(email), name = VALUES(name),
                 given_name = VALUES(given_name), family_name = VALUES(family_name),
                 picture_url = VALUES(picture_url), hosted_domain = VALUES(hosted_domain),
                 locale = VALUES(locale), login_count = login_count + 1, last_login = VALUES(last_login)""",
            (sub, email, user.get("name"), user.get("given_name"), user.get("family_name"),
             user.get("picture"), user.get("hd"), user.get("locale"), now, now),
        )
        cur.execute("SELECT id FROM admins WHERE google_sub = %s", (sub,))
        admin_id = cur.fetchone()[0]
        _admin_ids[email] = admin_id
        _auth_event(cur, "login", admin_id, email, sub, user.get("name"), ip, user_agent, None, now)

    _submit(job)


def auth_event(event, user=None, ip=None, user_agent=None, detail=None):
    user = user or {}
    email = (user.get("email") or "").lower() or None
    now = datetime.now()

    def job(cur):
        _auth_event(cur, event, _admin_id(cur, email), email, user.get("sub"),
                    user.get("name"), ip, user_agent, detail, now)

    _submit(job)


def _auth_event(cur, event, admin_id, email, sub, name, ip, user_agent, detail, when):
    cur.execute(
        """INSERT INTO auth_events (admin_id, event, email, google_sub, name, ip_address,
                                    user_agent, detail, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (admin_id, event, email, sub, name, ip, (user_agent or "")[:255] or None, detail, when),
    )


def _admin_id(cur, email):
    if not email:
        return None
    if email not in _admin_ids:
        cur.execute("SELECT id FROM admins WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return None
        _admin_ids[email] = row[0]
    return _admin_ids[email]


# ----------------------------------------------------------------------------
# Spots
# ----------------------------------------------------------------------------
def spot_changed(spot_id, old, new, old_since, when):
    def job(cur):
        cur.execute(
            """INSERT INTO spot_events (spot_id, from_status, to_status, duration_seconds, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (spot_id, old, new, max(0, int(when - old_since)), _dt(when)),
        )
        cur.execute("UPDATE spots SET status = %s, status_since = %s WHERE id = %s",
                    (new, _dt(when), spot_id))

    _submit(job)


def occupancy_snapshot(statuses, tracker_online):
    values = list(statuses.values())
    vacant = values.count("VACANT")
    occupied = values.count("OCCUPIED")
    violations = values.count("VIOLATION_DOUBLE_PARKED")
    total = len(values)
    pct = round((occupied + violations) / total * 100, 2) if total else 0
    now = datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO occupancy_snapshots (vacant, occupied, violations, total, occupancy_pct,
                                                tracker_online, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (vacant, occupied, violations, total, pct, tracker_online, now),
        )

    _submit(job)


# ----------------------------------------------------------------------------
# Violations and security alerts
# ----------------------------------------------------------------------------
def _key(spot_ids, started_at):
    return "+".join(spot_ids) + "@" + str(round(started_at, 3))


def violation_started(spot_ids, started_at, snapshot):
    key = _key(spot_ids, started_at)

    def job(cur):
        cur.execute(
            "INSERT INTO violations (spots_label, started_at, snapshot) VALUES (%s, %s, %s)",
            ("+".join(spot_ids), _dt(started_at), snapshot),
        )
        violation_id = cur.lastrowid
        _violation_ids[key] = violation_id
        cur.executemany("INSERT INTO violation_spots (violation_id, spot_id) VALUES (%s, %s)",
                        [(violation_id, s) for s in spot_ids])

    _submit(job)


def violation_cleared(spot_ids, started_at, cleared_at):
    key = _key(spot_ids, started_at)

    def job(cur):
        violation_id = _violation_ids.pop(key, None)
        if violation_id is None:
            # Server restarted mid-violation: close the open row for these spots
            cur.execute(
                """SELECT v.id FROM violations v JOIN violation_spots vs ON vs.violation_id = v.id
                   WHERE vs.spot_id IN %s AND v.cleared_at IS NULL ORDER BY v.id DESC LIMIT 1""",
                (tuple(spot_ids),),
            )
            row = cur.fetchone()
            if not row:
                return
            violation_id = row[0]
        cur.execute("UPDATE violations SET cleared_at = %s, duration_seconds = %s WHERE id = %s",
                    (_dt(cleared_at), max(0, int(cleared_at - started_at)), violation_id))

    _submit(job)


def security_alert(kind, spot_ids, started_at, ok, error=None, sent_by=None):
    key = _key(spot_ids, started_at)
    now = datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO security_alerts (violation_id, kind, sent_by, success, error, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (_violation_ids.get(key) or _last_violation_id(cur, spot_ids), kind,
             _admin_id(cur, sent_by), ok, (error or None) and error[:255], now),
        )

    _submit(job)


def _last_violation_id(cur, spot_ids):
    cur.execute("SELECT id FROM violations WHERE spots_label = %s ORDER BY id DESC LIMIT 1",
                ("+".join(spot_ids),))
    row = cur.fetchone()
    return row[0] if row else None


# ----------------------------------------------------------------------------
# Telegram subscribers
# ----------------------------------------------------------------------------
def subscriber_added(chat_id, since=None):
    when = _dt(since) if since else datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO telegram_subscribers (chat_id, active, subscribed_at)
               VALUES (%s, TRUE, %s)
               ON DUPLICATE KEY UPDATE active = TRUE, subscribed_at = VALUES(subscribed_at),
                 unsubscribed_at = NULL, unsubscribe_reason = NULL""",
            (int(chat_id), when),
        )

    _submit(job)


def subscriber_import(subscribers):
    """Copy existing subscribers.json entries in without touching newer rows."""
    def job(cur):
        cur.executemany(
            "INSERT IGNORE INTO telegram_subscribers (chat_id, active, subscribed_at) VALUES (%s, TRUE, %s)",
            [(int(cid), _dt(sub.get("since", time.time()))) for cid, sub in subscribers.items()],
        )

    if subscribers:
        _submit(job)


def subscriber_removed(chat_id, reason):
    now = datetime.now()

    def job(cur):
        cur.execute(
            """UPDATE telegram_subscribers SET active = FALSE, unsubscribed_at = %s, unsubscribe_reason = %s
               WHERE chat_id = %s""",
            (now, reason, int(chat_id)),
        )

    _submit(job)


def broadcast_sent(spot_id, delivered_ids, recipients):
    now = datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO availability_broadcasts (spot_id, recipients, delivered, created_at)
               VALUES (%s, %s, %s, %s)""",
            (spot_id, recipients, len(delivered_ids), now),
        )
        if delivered_ids:
            cur.executemany(
                """UPDATE telegram_subscribers SET last_notified_at = %s,
                     notifications_sent = notifications_sent + 1 WHERE chat_id = %s""",
                [(now, int(cid)) for cid in delivered_ids],
            )

    _submit(job)


# ----------------------------------------------------------------------------
# System health
# ----------------------------------------------------------------------------
def system_event(event, detail=None):
    now = datetime.now()

    def job(cur):
        cur.execute("INSERT INTO system_events (event, detail, created_at) VALUES (%s, %s, %s)",
                    (event, detail, now))

    _submit(job)
