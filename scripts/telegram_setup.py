"""Telegram bot configuration."""
import getpass
import time
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def save_to_env(values):
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    lines = [l for l in lines if l.split("=", 1)[0] not in values]
    lines += [f"{key}={value}" for key, value in values.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")
    ENV_PATH.chmod(0o600)


# Bot verification
token = getpass.getpass("Bot token: ").strip()
api = f"https://api.telegram.org/bot{token}"

me = httpx.get(f"{api}/getMe", timeout=15).json()
if not me.get("ok"):
    raise SystemExit("Invalid bot token.")
bot_name = me["result"]["username"]
print(f"Connected to @{bot_name}. Waiting for /start in the target chat...")

# Chat discovery
chats = {}
deadline = time.time() + 120
while time.time() < deadline and not chats:
    updates = httpx.get(f"{api}/getUpdates", params={"timeout": 20}, timeout=30).json()
    for update in updates.get("result", []):
        message = update.get("message") or update.get("my_chat_member") or {}
        chat = message.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("title") or chat.get("first_name") or str(chat["id"])

if not chats:
    raise SystemExit("No chat found.")

chat_list = list(chats.items())
if len(chat_list) == 1:
    chat_id, chat_name = chat_list[0]
else:
    for number, (cid, name) in enumerate(chat_list, 1):
        print(f"  {number}. {name}")
    choice = int(input("Select chat: "))
    chat_id, chat_name = chat_list[choice - 1]

# Save and test
save_to_env({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": str(chat_id)})

test = httpx.post(
    f"{api}/sendMessage",
    data={"chat_id": chat_id, "parse_mode": "HTML",
          "text": "✅ <b>Park Patrol is connected.</b>\nViolation alerts will appear in this chat."},
    timeout=15,
).json()

if test.get("ok"):
    print(f"Configuration saved. Alerts will be sent to: {chat_name}")
else:
    print("Configuration saved, but the test message failed:", test.get("description"))
