"""Environment configuration generator."""
import base64
import getpass
import secrets
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

if ENV_PATH.exists():
    answer = input(".env already exists. Overwrite it? (y/n) ").strip().lower()
    if answer != "y":
        raise SystemExit("Left .env unchanged.")

# Google OAuth credentials
client_id = input("Google Client ID: ").strip()
if not client_id.endswith(".apps.googleusercontent.com"):
    print("  Warning: a Client ID normally ends with .apps.googleusercontent.com")

client_secret = getpass.getpass("Google Client secret: ").strip()
if not client_secret:
    raise SystemExit("The client secret is empty. Nothing written.")

# Administrator accounts
emails = input("Admin emails (comma-separated): ").strip().lower()
email_list = [e.strip() for e in emails.split(",") if e.strip()]
if not email_list or any("@" not in e for e in email_list):
    raise SystemExit("Enter at least one valid email address. Nothing written.")

# Write configuration
lines = [
    f"GOOGLE_CLIENT_ID={client_id}",
    f"GOOGLE_CLIENT_SECRET={client_secret}",
    f"ADMIN_EMAILS={','.join(email_list)}",
    f"SESSION_SECRET={secrets.token_hex(32)}",
    f"TRACKER_API_KEY={secrets.token_urlsafe(32)}",
    f"DATA_ENCRYPTION_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}",
    "BASE_URL=http://localhost:8000",
    "HTTPS_ONLY=false",
]
ENV_PATH.write_text("\n".join(lines) + "\n")
ENV_PATH.chmod(0o600)

print("Configuration saved. Admins:", ", ".join(email_list))
