"""Encryption for personal data stored in MySQL.

Personal fields (admin email, name, photo link, Telegram chat IDs, camera
snapshots) are encrypted with AES-256-GCM before they reach the database, so
the database itself only ever holds unreadable ciphertext. Values the server
needs to look up (e.g. "is this the same admin as before?") are stored as
keyed HMAC-SHA256 fingerprints, which cannot be reversed.

Both keys are derived from DATA_ENCRYPTION_KEY, which lives only in the
server's environment (.env locally, the Render dashboard in production) and
never in the database or the repository. Losing it makes the encrypted data
unrecoverable, so keep a backup of it somewhere safe.
"""
import base64
import hashlib
import hmac
import os
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PREFIX = "v1:"
NONCE_BYTES = 12


def _derive(master, purpose):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b"parkpatrol " + purpose).derive(master)


def _load_keys():
    raw = os.environ.get("DATA_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None, None
    try:
        master = base64.urlsafe_b64decode(raw)
    except (ValueError, TypeError):
        master = b""
    if len(master) != 32:
        print("Encryption: DATA_ENCRYPTION_KEY must be 32 bytes in base64 "
              "(run: python scripts/generate_key.py); personal data will not be saved")
        return None, None
    return AESGCM(_derive(master, b"encryption")), _derive(master, b"lookup")


_aead, _lookup_key = _load_keys()
ENABLED = _aead is not None


def generate_key():
    """A new random master key in the format DATA_ENCRYPTION_KEY expects."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def lookup_hash(value):
    """Keyed one-way fingerprint for finding a row without decrypting it."""
    if value is None or not ENABLED:
        return None
    normalized = str(value).strip().lower().encode()
    return hmac.new(_lookup_key, normalized, hashlib.sha256).hexdigest()


def encrypt_bytes(data, context):
    """Encrypt bytes; `context` (e.g. "violations.snapshot") is bound to the ciphertext."""
    if data is None or not ENABLED:
        return None
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + _aead.encrypt(nonce, data, context.encode())


def decrypt_bytes(blob, context):
    if blob is None or not ENABLED:
        return None
    return _aead.decrypt(bytes(blob[:NONCE_BYTES]), bytes(blob[NONCE_BYTES:]), context.encode())


def encrypt(text, context):
    """Encrypt text into a printable string that fits a TEXT column."""
    if text is None or not ENABLED:
        return None
    return PREFIX + base64.b64encode(encrypt_bytes(str(text).encode(), context)).decode()


def decrypt(token, context):
    if not token or not ENABLED or not token.startswith(PREFIX):
        return None
    return decrypt_bytes(base64.b64decode(token[len(PREFIX):]), context).decode()
