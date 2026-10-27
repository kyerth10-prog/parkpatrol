"""Telegram notifications for parking violations."""
import html
import json
import os
import time
from datetime import datetime, timedelta, timezone

import httpx

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ENABLED = bool(BOT_TOKEN and CHAT_ID)

PH_TIME = timezone(timedelta(hours=8))
COOLDOWN_SECONDS = 120

_last_alert = {}


# ----------------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------------
def _clock(ts):
    return datetime.fromtimestamp(ts, PH_TIME).strftime("%I:%M %p").lstrip("0")


def _duration(seconds):
    minutes = int(seconds // 60)
    if minutes < 1:
        return f"{int(seconds)} sec"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min"


# ----------------------------------------------------------------------------
# Telegram API
# ----------------------------------------------------------------------------
def send_to(chat_id, text, photo=None, button=None):
    if not BOT_TOKEN:
        return False, "Telegram is not configured.", None
    api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if button and button[1].startswith("https://"):
        data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": button[0], "url": button[1]}]]})
    try:
        if photo:
            data["caption"] = text
            response = httpx.post(f"{api}/sendPhoto", data=data,
                                  files={"photo": ("snapshot.jpg", photo, "image/jpeg")}, timeout=15)
        else:
            data["text"] = text
            data["disable_web_page_preview"] = "true"
            response = httpx.post(f"{api}/sendMessage", data=data, timeout=15)
        result = response.json()
        if not result.get("ok"):
            print("Telegram message failed:", result.get("description"))
            return False, result.get("description", "Telegram refused the message."), result.get("error_code")
        return True, "", None
    except (httpx.HTTPError, ValueError) as error:
        print("Telegram message failed:", error)
        return False, "Could not reach Telegram.", None


def _send(text, photo=None):
    if not ENABLED:
        return False, "Telegram alerts are not configured."
    ok, error, _ = send_to(CHAT_ID, text, photo)
    return ok, error


# ----------------------------------------------------------------------------
# Violation alerts
# ----------------------------------------------------------------------------
def _spots_label(spot_ids):
    names = " + ".join(f"<b>{html.escape(s)}</b>" for s in spot_ids)
    return ("Spots " if len(spot_ids) > 1 else "Spot ") + names


def violation_started(spot_ids, started_at, photo, base_url):
    key = "+".join(spot_ids)
    now = time.time()
    if now - _last_alert.get(key, 0) < COOLDOWN_SECONDS:
        return
    _last_alert[key] = now
    text = (
        f"🚨 <b>Double-parking detected</b>\n"
        f"{_spots_label(spot_ids)} · Lot A · {_clock(started_at)}\n\n"
        f'<a href="{html.escape(base_url)}/admin#violations">Open dashboard</a>'
    )
    return _send(text, photo)


def violation_cleared(spot_ids, started_at):
    text = (
        f"✅ <b>Cleared</b> · {_spots_label(spot_ids)}\n"
        f"Violation lasted {_duration(time.time() - started_at)}."
    )
    return _send(text)


def manual_alert(spot_ids, started_at, photo, sent_by, base_url):
    text = (
        f"📣 <b>Security requested</b>\n"
        f"{_spots_label(spot_ids)} double-parked for "
        f"{_duration(time.time() - started_at)}.\n"
        f"Sent by {html.escape(sent_by)}\n\n"
        f'<a href="{html.escape(base_url)}/admin#violations">Open dashboard</a>'
    )
    return _send(text, photo)
