"""Telegram bot for public spot-availability subscriptions."""
import json
import os
import threading
import time
from pathlib import Path

import httpx

from services import database
from services import telegram_alerts as tg

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"
COOLDOWN_SECONDS = float(os.environ.get("NOTIFY_COOLDOWN_MINUTES", "15")) * 60

_lock = threading.Lock()
_subscribers = {}
_get_statuses = None
_base_url = ""
bot_username = None


# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
def _load():
    global _subscribers
    try:
        _subscribers = json.loads(DATA_FILE.read_text())
    except (FileNotFoundError, ValueError):
        _subscribers = {}
    database.subscriber_import(_subscribers)


def _save():
    DATA_FILE.parent.mkdir(exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_subscribers, indent=1))
    tmp.replace(DATA_FILE)


def subscriber_count():
    return len(_subscribers)


def link():
    return f"https://t.me/{bot_username}?start=notify" if bot_username else None


# ----------------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------------
def _availability():
    values = list(_get_statuses().values())
    free = sum(1 for s in values if s == "VACANT")
    return free, len(values)


def _status_text():
    free, total = _availability()
    if free == 0:
        return f"🔴 <b>Lot A is full</b> (0 of {total} free)."
    return f"🟢 <b>{free} of {total} spots free</b> at Lot A right now."


def _reply(chat_id, text):
    tg.send_to(chat_id, text, button=("View live map", _base_url))


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
def _handle(message):
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    text = (message.get("text") or "").strip()
    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    private = chat.get("type") == "private"

    if command == "/status":
        _reply(chat_id, _status_text())
        return
    if not private:
        return

    if command == "/start":
        with _lock:
            already = chat_id in _subscribers
            if not already:
                _subscribers[chat_id] = {"since": time.time(), "last_notified": 0}
                _save()
                database.subscriber_added(chat_id)
        if already:
            _reply(chat_id, "You're already subscribed. 👍\n\n" + _status_text())
        else:
            _reply(chat_id,
                   "👋 <b>You're subscribed to Park Patrol!</b>\n"
                   "I'll message you whenever DLSL Lot A is <b>full and a spot opens up</b>.\n\n"
                   + _status_text() +
                   "\n\n/status – check availability anytime\n/stop – unsubscribe")
    elif command == "/stop":
        with _lock:
            removed = _subscribers.pop(chat_id, None) is not None
            if removed:
                _save()
                database.subscriber_removed(chat_id, "stop")
        _reply(chat_id, "🔕 You're unsubscribed. Send /start anytime to turn alerts back on."
               if removed else "You weren't subscribed. Send /start to get alerts.")
    else:
        _reply(chat_id, "Send /start to get spot alerts, /status to check the lot, or /stop to unsubscribe.")


# ----------------------------------------------------------------------------
# Broadcast
# ----------------------------------------------------------------------------
def spot_opened(spot_id):
    now = time.time()
    with _lock:
        targets = [cid for cid, sub in _subscribers.items()
                   if now - sub.get("last_notified", 0) >= COOLDOWN_SECONDS]
    text = (f"🟢 <b>A spot just opened!</b>\n"
            f"Spot <b>{spot_id}</b> at DLSL Lot A is free right now. Spots go fast!\n\n"
            f"<i>Send /stop to unsubscribe.</i>")
    delivered = []
    for chat_id in targets:
        ok, _, code = tg.send_to(chat_id, text, button=("View live map", _base_url))
        with _lock:
            if code == 403:
                _subscribers.pop(chat_id, None)
                database.subscriber_removed(chat_id, "blocked")
            elif ok and chat_id in _subscribers:
                _subscribers[chat_id]["last_notified"] = now
                delivered.append(chat_id)
        time.sleep(0.05)
    if targets:
        with _lock:
            _save()
        database.broadcast_sent(spot_id, delivered, len(targets))


# ----------------------------------------------------------------------------
# Update polling
# ----------------------------------------------------------------------------
def _run():
    global bot_username
    api = f"https://api.telegram.org/bot{tg.BOT_TOKEN}"
    while bot_username is None:
        try:
            me = httpx.get(f"{api}/getMe", timeout=15).json()
            if not me.get("ok"):
                print("Telegram bot: token rejected -", me.get("description"))
                return
            bot_username = me["result"]["username"]
            print(f"Telegram bot @{bot_username} is listening ({subscriber_count()} subscribers)")
        except (httpx.HTTPError, ValueError):
            time.sleep(10)

    offset = None
    while True:
        try:
            result = httpx.get(f"{api}/getUpdates",
                               params={"timeout": 25, "offset": offset, "allowed_updates": '["message"]'},
                               timeout=35).json()
        except (httpx.HTTPError, ValueError):
            time.sleep(5)
            continue
        if not result.get("ok"):
            print("Telegram bot:", result.get("description"))
            time.sleep(10)
            continue
        for update in result["result"]:
            offset = update["update_id"] + 1
            if "message" in update:
                try:
                    _handle(update["message"])
                except Exception as error:
                    print("Telegram bot error:", error)


def start(get_statuses, base_url):
    global _get_statuses, _base_url
    _get_statuses = get_statuses
    _base_url = base_url
    if not tg.BOT_TOKEN:
        return
    _load()
    threading.Thread(target=_run, daemon=True, name="telegram-bot").start()
