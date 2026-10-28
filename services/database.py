"""MySQL storage for Park Patrol.

Writes go through a single background worker so a slow or offline database
never delays the tracker or the dashboard. If MySQL is unreachable the server
keeps running from memory and retries the connection.
"""
import os
import queue
import re
import ssl
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pymysql

from services import crypto

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "database" / "schema.sql"

HOST = os.environ.get("DB_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("DB_PORT", "3306"))
USER = os.environ.get("DB_USER", "root").strip()
PASSWORD = os.environ.get("DB_PASSWORD", "")
NAME = os.environ.get("DB_NAME", "parkpatrol").strip()
ENABLED = os.environ.get("DB_ENABLED", "true").lower() != "false"
# Hosted MySQL (e.g. Aiven) needs TLS. DB_SSL_CA is the provider's CA
# certificate: a file path, or its PEM text pasted into an environment variable.
SSL_ENABLED = os.environ.get("DB_SSL", "false").lower() == "true"
SSL_CA = os.environ.get("DB_SSL_CA", "").strip().strip("'\"")

RETRY_SECONDS = 15

_jobs = queue.Queue(maxsize=10_000)
_conn = None          # used only by the writer thread
_started = False
_last_failure = 0.0
_warned = False
_violation_ids = {}
_admin_ids = {}


# ----------------------------------------------------------------------------
# Connection
# ----------------------------------------------------------------------------
def _dt(ts):
    return datetime.fromtimestamp(ts) if ts is not None else None


def _ssl_context():
    """Verified TLS context; the server certificate is always checked."""
    if not SSL_ENABLED:
        return None
    if "BEGIN CERTIFICATE" in SSL_CA:
        handle = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        handle.write(SSL_CA.replace("\\n", "\n"))
        handle.close()
        return ssl.create_default_context(cafile=handle.name)
    return ssl.create_default_context(cafile=SSL_CA or None)


_SSL = _ssl_context()


def _connect(database=NAME):
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, database=database,
        charset="utf8mb4", autocommit=True, connect_timeout=10, ssl=_SSL,
    )


def _connection():
    """The writer thread's connection (never shared with other threads)."""
    global _conn, _last_failure, _warned
    if _conn is not None:
        try:
            _conn.ping(reconnect=True)
            return _conn
        except Exception:
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
            _migrate(cur)
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Migration: plain-text personal data -> encrypted (databases created before
# encryption was added). Each step runs only when the old columns still exist.
# ----------------------------------------------------------------------------
def _columns(cur, table):
    cur.execute("SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s", (table,))
    return {row[0].lower() for row in cur.fetchall()}


def _migrate(cur):
    # Sign-in log: keep only the outcome; this step needs no key.
    if "email" in _columns(cur, "auth_events"):
        cur.execute("ALTER TABLE auth_events ADD COLUMN result ENUM('ok', 'invalid') NOT NULL DEFAULT 'ok' AFTER event")
        cur.execute("UPDATE auth_events SET result = 'invalid', event = 'login' "
                    "WHERE event IN ('denied', 'unverified', 'error')")
        cur.execute("ALTER TABLE auth_events MODIFY event ENUM('login', 'logout') NOT NULL, "
                    "MODIFY result ENUM('ok', 'invalid') NOT NULL, "
                    "DROP COLUMN email, DROP COLUMN google_sub, DROP COLUMN name, "
                    "DROP COLUMN ip_address, DROP COLUMN user_agent, DROP COLUMN detail")
        print("Database: sign-in log reduced to ok / invalid")

    # Violations can be marked as handled by security
    if "resolved_at" not in _columns(cur, "violations"):
        cur.execute("ALTER TABLE violations ADD COLUMN resolved_at DATETIME(3) NULL, "
                    "ADD COLUMN resolved_by INT UNSIGNED NULL, "
                    "ADD CONSTRAINT fk_violations_resolver FOREIGN KEY (resolved_by) "
                    "REFERENCES admins (id) ON DELETE SET NULL")
        print("Database: violations can now be marked as resolved")

    old_admins = "email" in _columns(cur, "admins")
    old_subscribers = "chat_id" in _columns(cur, "telegram_subscribers")
    old_snapshots = "snapshot" in _columns(cur, "violations")
    if not (old_admins or old_subscribers or old_snapshots):
        return
    if not crypto.ENABLED:
        print("Database: plain-text personal data found; set DATA_ENCRYPTION_KEY to encrypt it")
        return

    if old_admins:
        cur.execute("ALTER TABLE admins ADD COLUMN account_hash CHAR(64) NULL AFTER id, "
                    "ADD COLUMN email_hash CHAR(64) NULL AFTER account_hash, "
                    "ADD COLUMN email_enc TEXT NULL AFTER email_hash, "
                    "ADD COLUMN name_enc TEXT NULL AFTER email_enc, "
                    "ADD COLUMN picture_enc TEXT NULL AFTER name_enc")
        cur.execute("SELECT id, google_sub, email, name, picture_url FROM admins")
        for admin_id, sub, email, name, picture in cur.fetchall():
            cur.execute("UPDATE admins SET account_hash = %s, email_hash = %s, email_enc = %s, "
                        "name_enc = %s, picture_enc = %s WHERE id = %s",
                        (crypto.lookup_hash(sub), crypto.lookup_hash(email),
                         crypto.encrypt(email.lower(), "admins.email"),
                         crypto.encrypt(name, "admins.name"),
                         crypto.encrypt(picture, "admins.picture"), admin_id))
        cur.execute("ALTER TABLE admins DROP COLUMN google_sub, DROP COLUMN email, DROP COLUMN name, "
                    "DROP COLUMN given_name, DROP COLUMN family_name, DROP COLUMN picture_url, "
                    "DROP COLUMN hosted_domain, DROP COLUMN locale, "
                    "MODIFY account_hash CHAR(64) NOT NULL, MODIFY email_hash CHAR(64) NOT NULL, "
                    "MODIFY email_enc TEXT NOT NULL, "
                    "ADD UNIQUE KEY uq_admins_account (account_hash), ADD UNIQUE KEY uq_admins_email (email_hash)")
        print("Database: admin accounts encrypted")

    if old_subscribers:
        cur.execute("ALTER TABLE telegram_subscribers ADD COLUMN chat_hash CHAR(64) NULL, "
                    "ADD COLUMN chat_id_enc TEXT NULL")
        cur.execute("SELECT chat_id FROM telegram_subscribers")
        for (chat_id,) in cur.fetchall():
            cur.execute("UPDATE telegram_subscribers SET chat_hash = %s, chat_id_enc = %s WHERE chat_id = %s",
                        (crypto.lookup_hash(chat_id), crypto.encrypt(chat_id, "subscribers.chat_id"), chat_id))
        cur.execute("ALTER TABLE telegram_subscribers DROP PRIMARY KEY, DROP COLUMN chat_id, "
                    "ADD COLUMN id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY FIRST, "
                    "MODIFY chat_hash CHAR(64) NOT NULL AFTER id, MODIFY chat_id_enc TEXT NOT NULL AFTER chat_hash, "
                    "ADD UNIQUE KEY uq_subscribers_chat (chat_hash)")
        print("Database: Telegram subscribers encrypted")

    if old_snapshots:
        cur.execute("ALTER TABLE violations ADD COLUMN snapshot_enc MEDIUMBLOB NULL AFTER duration_seconds")
        cur.execute("SELECT id, snapshot FROM violations WHERE snapshot IS NOT NULL")
        for violation_id, snapshot in cur.fetchall():
            cur.execute("UPDATE violations SET snapshot_enc = %s WHERE id = %s",
                        (crypto.encrypt_bytes(bytes(snapshot), "violations.snapshot"), violation_id))
        cur.execute("ALTER TABLE violations DROP COLUMN snapshot")
        print("Database: violation snapshots encrypted")


@contextmanager
def _reader():
    """A short-lived connection for reads made outside the writer thread."""
    try:
        conn = _connect()
    except pymysql.MySQLError as error:
        print("Database: MySQL unavailable for reading:", error)
        yield None
        return
    try:
        with conn.cursor() as cur:
            yield cur
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
    global _started
    if not ENABLED:
        return {}
    if not crypto.ENABLED:
        print("Encryption: DATA_ENCRYPTION_KEY not set; admin details, subscribers and "
              "snapshots will not be saved to MySQL")
    try:
        _create_schema()
    except pymysql.MySQLError as error:
        print(f"Database: could not prepare MySQL ({error}); running without saving history")
    if not _started:
        _started = True
        threading.Thread(target=_worker, daemon=True, name="database").start()
    return load_spots()


def sync_spots(spot_ids):
    """Make the spots table match the current lot layout (one row on the right).

    Spots left over from an older layout are removed when nothing refers to
    them; ones with history are kept so past events stay intact.
    """
    if not ENABLED:
        return
    try:
        with _reader() as cur:
            if cur is None:
                return
            for position, spot_id in enumerate(spot_ids, start=1):
                cur.execute(
                    """INSERT INTO spots (id, side, position, status_since) VALUES (%s, 'right', %s, NOW(3))
                       ON DUPLICATE KEY UPDATE side = 'right', position = VALUES(position)""",
                    (spot_id, position),
                )
            placeholders = ", ".join(["%s"] * len(spot_ids))
            cur.execute(
                f"""DELETE FROM spots WHERE id NOT IN ({placeholders})
                      AND id NOT IN (SELECT spot_id FROM spot_events)
                      AND id NOT IN (SELECT spot_id FROM violation_spots)
                      AND id NOT IN (SELECT spot_id FROM availability_broadcasts)""",
                spot_ids,
            )
    except pymysql.MySQLError as error:
        print("Database error:", error)


def load_spots():
    try:
        with _reader() as cur:
            if cur is None:
                return {}
            cur.execute("SELECT id, status, status_since FROM spots")
            return {row[0]: (row[1], row[2].timestamp()) for row in cur.fetchall()}
    except pymysql.MySQLError as error:
        print("Database error:", error)
        return {}


def _events(where, params, limit):
    try:
        with _reader() as cur:
            if cur is None:
                return None
            cur.execute(
                f"""SELECT spot_id, from_status, to_status, created_at FROM spot_events
                    {where} ORDER BY created_at DESC, id DESC LIMIT %s""",
                (*params, limit),
            )
            return [{"spot_id": spot, "from": old, "to": new, "time": when.timestamp()}
                    for spot, old, new, when in cur.fetchall()]
    except pymysql.MySQLError as error:
        print("Database error:", error)
        return None


def recent_events(limit=100):
    """The newest spot changes, newest first (empty if MySQL is unavailable)."""
    return (_events("", (), limit) or []) if ENABLED else []


def events_since(ts, limit=20000):
    """Spot changes since a time, newest first; None if MySQL is unavailable."""
    return _events("WHERE created_at >= %s", (_dt(ts),), limit) if ENABLED else None


# ----------------------------------------------------------------------------
# Admins and sign-in
# ----------------------------------------------------------------------------
def admin_login(user):
    """Record a successful sign-in. Identity is stored encrypted / as fingerprints only."""
    now = datetime.now()
    email = (user.get("email") or "").lower()

    def job(cur):
        admin_id = None
        if crypto.ENABLED:
            cur.execute(
                """INSERT INTO admins (account_hash, email_hash, email_enc, name_enc, picture_enc,
                                       login_count, first_login, last_login)
                   VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                   ON DUPLICATE KEY UPDATE email_hash = VALUES(email_hash), email_enc = VALUES(email_enc),
                     name_enc = VALUES(name_enc), picture_enc = VALUES(picture_enc),
                     login_count = login_count + 1, last_login = VALUES(last_login)""",
                (crypto.lookup_hash(user.get("sub")), crypto.lookup_hash(email),
                 crypto.encrypt(email, "admins.email"), crypto.encrypt(user.get("name"), "admins.name"),
                 crypto.encrypt(user.get("picture"), "admins.picture"), now, now),
            )
            admin_id = _admin_id(cur, email, refresh=True)
        _auth_event(cur, "login", "ok", admin_id, now)

    _submit(job)


def auth_event(event, ok, email=None):
    """Log a sign-in outcome. Failed attempts store nothing about who tried."""
    now = datetime.now()

    def job(cur):
        _auth_event(cur, event, "ok" if ok else "invalid", _admin_id(cur, email) if ok else None, now)

    _submit(job)


def _auth_event(cur, event, result, admin_id, when):
    cur.execute("INSERT INTO auth_events (admin_id, event, result, created_at) VALUES (%s, %s, %s, %s)",
                (admin_id, event, result, when))


def _admin_id(cur, email, refresh=False):
    if not email or not crypto.ENABLED:
        return None
    email = email.lower()
    if refresh or email not in _admin_ids:
        cur.execute("SELECT id FROM admins WHERE email_hash = %s", (crypto.lookup_hash(email),))
        row = cur.fetchone()
        if not row:
            return None
        _admin_ids[email] = row[0]
    return _admin_ids[email]


def list_admins():
    """Decrypted admin list, for display inside the app only."""
    if not (ENABLED and crypto.ENABLED):
        return []
    with _reader() as cur:
        if cur is None:
            return []
        cur.execute("SELECT id, email_enc, name_enc, login_count, last_login FROM admins ORDER BY last_login DESC")
        return [
            {"id": admin_id, "email": crypto.decrypt(email, "admins.email"),
             "name": crypto.decrypt(name, "admins.name"), "logins": count, "last_login": last}
            for admin_id, email, name, count, last in cur.fetchall()
        ]


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
            "INSERT INTO violations (spots_label, started_at, snapshot_enc) VALUES (%s, %s, %s)",
            ("+".join(spot_ids), _dt(started_at), crypto.encrypt_bytes(snapshot, "violations.snapshot")),
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


def violation_resolved(spot_ids, started_at, admin_email):
    key = _key(spot_ids, started_at)
    now = datetime.now()

    def job(cur):
        violation_id = _violation_ids.get(key) or _last_violation_id(cur, spot_ids)
        if violation_id is None:
            return
        cur.execute("UPDATE violations SET resolved_at = %s, resolved_by = %s WHERE id = %s AND resolved_at IS NULL",
                    (now, _admin_id(cur, admin_email), violation_id))

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
def load_subscribers():
    """Active subscribers saved in MySQL, decrypted into the shape telegram_bot keeps them."""
    if not (ENABLED and crypto.ENABLED):
        return {}
    try:
        with _reader() as cur:
            if cur is None:
                return {}
            cur.execute("SELECT chat_id_enc, subscribed_at, last_notified_at FROM telegram_subscribers WHERE active")
            return {
                crypto.decrypt(chat_enc, "subscribers.chat_id"): {
                    "since": subscribed.timestamp(),
                    "last_notified": notified.timestamp() if notified else 0,
                }
                for chat_enc, subscribed, notified in cur.fetchall()
            }
    except Exception as error:
        print("Database error:", error)
        return {}


def _subscriber_row(chat_id):
    return crypto.lookup_hash(chat_id), crypto.encrypt(str(chat_id), "subscribers.chat_id")


def subscriber_added(chat_id, since=None):
    when = _dt(since) if since else datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO telegram_subscribers (chat_hash, chat_id_enc, active, subscribed_at)
               VALUES (%s, %s, TRUE, %s)
               ON DUPLICATE KEY UPDATE active = TRUE, subscribed_at = VALUES(subscribed_at),
                 unsubscribed_at = NULL, unsubscribe_reason = NULL""",
            (*_subscriber_row(chat_id), when),
        )

    if crypto.ENABLED:
        _submit(job)


def subscriber_import(subscribers):
    """Copy existing subscribers.json entries in without touching newer rows."""
    def job(cur):
        cur.executemany(
            "INSERT IGNORE INTO telegram_subscribers (chat_hash, chat_id_enc, active, subscribed_at) "
            "VALUES (%s, %s, TRUE, %s)",
            [(*_subscriber_row(cid), _dt(sub.get("since", time.time()))) for cid, sub in subscribers.items()],
        )

    if subscribers and crypto.ENABLED:
        _submit(job)


def subscriber_removed(chat_id, reason):
    now = datetime.now()

    def job(cur):
        cur.execute(
            """UPDATE telegram_subscribers SET active = FALSE, unsubscribed_at = %s, unsubscribe_reason = %s
               WHERE chat_hash = %s""",
            (now, reason, crypto.lookup_hash(chat_id)),
        )

    if crypto.ENABLED:
        _submit(job)


def broadcast_sent(spot_id, delivered_ids, recipients):
    now = datetime.now()

    def job(cur):
        cur.execute(
            """INSERT INTO availability_broadcasts (spot_id, recipients, delivered, created_at)
               VALUES (%s, %s, %s, %s)""",
            (spot_id, recipients, len(delivered_ids), now),
        )
        if delivered_ids and crypto.ENABLED:
            cur.executemany(
                """UPDATE telegram_subscribers SET last_notified_at = %s,
                     notifications_sent = notifications_sent + 1 WHERE chat_hash = %s""",
                [(now, crypto.lookup_hash(cid)) for cid in delivered_ids],
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
