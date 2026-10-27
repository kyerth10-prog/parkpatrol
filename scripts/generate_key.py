"""Print a new DATA_ENCRYPTION_KEY for encrypting personal data in MySQL.

Generate it once, put the same value in .env and in Render, and keep a backup:
data encrypted with a key cannot be read without that exact key.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.crypto import generate_key  # noqa: E402

print(generate_key())
