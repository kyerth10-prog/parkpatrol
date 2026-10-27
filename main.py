"""Park Patrol web server."""
import asyncio
import os
import secrets
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import List, Optional

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from services import database, telegram_alerts, telegram_bot  # noqa: E402


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


GOOGLE_CLIENT_ID = require_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = require_env("GOOGLE_CLIENT_SECRET")
SESSION_SECRET = require_env("SESSION_SECRET")
TRACKER_API_KEY = require_env("TRACKER_API_KEY")
ADMIN_EMAILS = {e.strip().lower() for e in require_env("ADMIN_EMAILS").split(",") if e.strip()}
ON_RENDER = bool(os.environ.get("RENDER"))
BASE_URL = (os.environ.get("BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:8000").rstrip("/")
HTTPS_ONLY = os.environ.get("HTTPS_ONLY", "true" if ON_RENDER else "false").lower() == "true"


# ----------------------------------------------------------------------------
# Application and middleware
# ----------------------------------------------------------------------------
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=HTTPS_ONLY,
    max_age=60 * 60 * 24,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if HTTPS_ONLY and request.url.hostname in LOCAL_HOSTS:
        response.raw_headers[:] = [
            (k, v.replace(b"; secure", b"") if k == b"set-cookie" else v)
            for k, v in response.raw_headers
        ]
    return response


oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
SPOT_IDS = [f"A{i}" for i in range(1, 7)]   # Lot A: 3 covered bays x 2 spots, A1 at the top
VALID_STATUSES = {"VACANT", "OCCUPIED", "VIOLATION_DOUBLE_PARKED"}
VIOLATION = "VIOLATION_DOUBLE_PARKED"
MAX_SPOTS_PER_UPDATE = 3
MAX_FRAME_BYTES = 2_000_000
MAX_STREAM_FPS = 30
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
TRACKER_TIMEOUT = 15
SNAPSHOT_SECONDS = 300

now = time.time()
statuses = {spot_id: "VACANT" for spot_id in SPOT_IDS}
since = {spot_id: now for spot_id in SPOT_IDS}
events = deque(maxlen=100)
latest_frame = {"jpeg": None, "seq": 0, "time": None}
tracker_seen = {"time": None, "online": False}
violation_groups = {}
group_info = {}


class StatusUpdate(BaseModel):
    spot_id: Optional[str] = None
    spot_ids: Optional[List[str]] = None
    status: str


class AlertRequest(BaseModel):
    spot_id: str


# ----------------------------------------------------------------------------
# Access control
# ----------------------------------------------------------------------------
def require_tracker_key(x_api_key: Optional[str] = Header(default=None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, TRACKER_API_KEY):
        raise HTTPException(status_code=401, detail="Bad API key.")


def require_admin(request: Request):
    email = request.session.get("admin_email")
    if not email or email not in ADMIN_EMAILS:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return email


# ----------------------------------------------------------------------------
# Public routes
# ----------------------------------------------------------------------------
def public_view():
    return {
        spot_id: "available" if status == "VACANT" else "taken"
        for spot_id, status in statuses.items()
    }


@app.get("/")
def public_page():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/api/spots")
def get_spots():
    return public_view()


@app.get("/api/notify")
def notify_info():
    return {"telegram_link": telegram_bot.link()}


# ----------------------------------------------------------------------------
# Tracker routes
# ----------------------------------------------------------------------------
def requested_spots(update):
    ids = list(dict.fromkeys(update.spot_ids or ([update.spot_id] if update.spot_id else [])))
    if not ids or len(ids) > MAX_SPOTS_PER_UPDATE:
        raise HTTPException(status_code=400, detail="Provide 1 to 3 spots.")
    if any(spot_id not in statuses for spot_id in ids):
        raise HTTPException(status_code=400, detail="Unknown spot.")
    return ids


def mark_tracker_seen(current_time):
    if not tracker_seen["online"]:
        last = tracker_seen["time"]
        detail = "First data since server start" if last is None else f"Back after {int(current_time - last)} s without data"
        database.system_event("tracker_online", detail)
        tracker_seen["online"] = True
    tracker_seen["time"] = current_time


def notify_violation_started(spot_ids, started, photo):
    result = telegram_alerts.violation_started(spot_ids, started, photo, BASE_URL)
    if result is not None and telegram_alerts.ENABLED:
        database.security_alert("detected", spot_ids, started, *result)


def notify_violation_cleared(spot_ids, started):
    database.violation_cleared(spot_ids, started, time.time())
    result = telegram_alerts.violation_cleared(spot_ids, started)
    if telegram_alerts.ENABLED:
        database.security_alert("cleared", spot_ids, started, *result)


def leave_group(spot_id, background=None):
    group = violation_groups.pop(spot_id, None)
    if not group:
        return
    info = group_info.pop(group, {"started": since[spot_id], "origin": group})
    remaining = tuple(s for s in group if violation_groups.get(s) == group)
    if remaining:
        for s in remaining:
            violation_groups[s] = remaining
        group_info[remaining] = info
    elif background is not None:
        background.add_task(notify_violation_cleared, list(info["origin"]), info["started"])


@app.post("/api/status")
def update_status(update: StatusUpdate, background: BackgroundTasks, _: None = Depends(require_tracker_key)):
    ids = requested_spots(update)
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status.")

    current_time = time.time()
    mark_tracker_seen(current_time)
    lot_was_full = "VACANT" not in statuses.values()

    changed = []
    for spot_id in ids:
        old = statuses[spot_id]
        if old != update.status:
            database.spot_changed(spot_id, old, update.status, since[spot_id], current_time)
            statuses[spot_id] = update.status
            since[spot_id] = current_time
            events.appendleft(
                {"spot_id": spot_id, "from": old, "to": update.status, "time": current_time}
            )
            changed.append((spot_id, old))

    # Violations
    if update.status == VIOLATION:
        group = tuple(ids)
        if any(violation_groups.get(s) != group for s in ids):
            for s in ids:
                leave_group(s)
            started = min(since[s] for s in ids)
            for s in ids:
                violation_groups[s] = group
            group_info[group] = {"started": started, "origin": group}
            database.violation_started(list(group), started, latest_frame["jpeg"])
            background.add_task(notify_violation_started, list(group), started, latest_frame["jpeg"])
    else:
        for spot_id, old in changed:
            if old == VIOLATION:
                leave_group(spot_id, background)

    # Availability
    if lot_was_full and update.status == "VACANT" and changed:
        background.add_task(telegram_bot.spot_opened, changed[0][0])
    return {"ok": True}


@app.post("/api/frame")
async def upload_frame(request: Request, _: None = Depends(require_tracker_key)):
    data = await request.body()
    if len(data) > MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="Frame too large.")
    if not data.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="Not a JPEG.")
    latest_frame["jpeg"] = data
    latest_frame["seq"] += 1
    latest_frame["time"] = time.time()
    mark_tracker_seen(latest_frame["time"])
    return {"ok": True}


# ----------------------------------------------------------------------------
# Admin routes
# ----------------------------------------------------------------------------
@app.get("/admin")
def admin_page(request: Request):
    email = request.session.get("admin_email")
    if not email or email not in ADMIN_EMAILS:
        return RedirectResponse(url="/login")
    return FileResponse(BASE_DIR / "private" / "admin.html")


@app.get("/api/admin/state")
def admin_state(request: Request, admin: str = Depends(require_admin)):
    return {
        "signed_in_as": admin,
        "admin": {
            "email": admin,
            "name": request.session.get("admin_name"),
            "picture": request.session.get("admin_picture"),
        },
        "server_time": time.time(),
        "tracker_seen": tracker_seen["time"],
        "spots": {
            spot_id: {
                "status": statuses[spot_id],
                "since": since[spot_id],
                "group": list(violation_groups[spot_id]) if spot_id in violation_groups else None,
            }
            for spot_id in SPOT_IDS
        },
        "events": list(events)[:30],
        "telegram_enabled": telegram_alerts.ENABLED,
        "frame_time": latest_frame["time"],
    }


@app.get("/api/admin/frame")
def admin_frame(admin: str = Depends(require_admin)):
    if latest_frame["jpeg"] is None:
        raise HTTPException(status_code=404, detail="No frame yet.")
    return Response(
        content=latest_frame["jpeg"],
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/admin/stream")
async def admin_stream(request: Request, fps: float = 15, admin: str = Depends(require_admin)):
    interval = 1 / max(1.0, min(fps, MAX_STREAM_FPS))

    async def frames():
        sent_seq, sent_at = None, 0.0
        while not await request.is_disconnected():
            data, seq = latest_frame["jpeg"], latest_frame["seq"]
            now = time.monotonic()
            if data is not None and seq != sent_seq and now - sent_at >= interval:
                sent_seq, sent_at = seq, now
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
            await asyncio.sleep(0.01)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/admin/alert")
def admin_alert(body: AlertRequest, admin: str = Depends(require_admin)):
    if statuses.get(body.spot_id) != VIOLATION:
        raise HTTPException(status_code=400, detail="That spot has no active violation.")
    group = violation_groups.get(body.spot_id, (body.spot_id,))
    started = group_info.get(group, {}).get("started", since[body.spot_id])
    ok, error = telegram_alerts.manual_alert(
        list(group), started, latest_frame["jpeg"], admin, BASE_URL
    )
    database.security_alert("manual", list(group), started, ok, error, sent_by=admin)
    if not ok:
        raise HTTPException(status_code=503, detail=error)
    return {"ok": True}


# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------
def auth_base(request: Request):
    if request.url.hostname in LOCAL_HOSTS:
        return f"{request.url.scheme}://{request.url.netloc}"
    return BASE_URL


@app.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, f"{auth_base(request)}/auth")


@app.get("/auth")
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        print("Sign-in failed:", error)
        database.auth_event("login", ok=False)
        raise HTTPException(status_code=400, detail="Sign-in failed. Please try again.")

    user = token.get("userinfo") or {}
    email = (user.get("email") or "").lower()
    if not user.get("email_verified"):
        database.auth_event("login", ok=False)
        raise HTTPException(status_code=403, detail="This Google account is not allowed.")
    if email not in ADMIN_EMAILS:
        database.auth_event("login", ok=False)
        raise HTTPException(status_code=403, detail="This Google account is not allowed.")

    database.admin_login(user)
    request.session.clear()
    request.session["admin_email"] = email
    request.session["admin_name"] = user.get("name")
    request.session["admin_picture"] = user.get("picture")
    return RedirectResponse(url="/admin")


@app.get("/logout")
def logout(request: Request):
    email = request.session.get("admin_email")
    if email:
        database.auth_event("logout", ok=True, email=email)
    request.session.clear()
    return RedirectResponse(url="/")


# ----------------------------------------------------------------------------
# Startup
# ----------------------------------------------------------------------------
def restore_spots():
    saved = database.start()          # creates the tables first
    database.sync_spots(SPOT_IDS)     # then matches the spots table to the current layout
    for spot_id, (status, status_since) in saved.items():
        if spot_id in statuses and status in VALID_STATUSES:
            statuses[spot_id] = status
            since[spot_id] = status_since
            if status == VIOLATION:
                violation_groups[spot_id] = (spot_id,)
                group_info[(spot_id,)] = {"started": status_since, "origin": (spot_id,)}


def monitor():
    """Record tracker outages and lot occupancy in the background."""
    next_snapshot = time.time() + 30
    while True:
        time.sleep(5)
        current_time = time.time()
        last = tracker_seen["time"]
        if tracker_seen["online"] and last is not None and current_time - last > TRACKER_TIMEOUT:
            tracker_seen["online"] = False
            database.system_event("tracker_offline", f"No data for {TRACKER_TIMEOUT} s")
        if current_time >= next_snapshot:
            next_snapshot = current_time + SNAPSHOT_SECONDS
            database.occupancy_snapshot(dict(statuses), tracker_seen["online"])


@app.on_event("startup")
def start_services():
    restore_spots()
    database.system_event("server_started", BASE_URL)
    threading.Thread(target=monitor, daemon=True, name="monitor").start()
    telegram_bot.start(lambda: dict(statuses), BASE_URL)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def local_addresses():
    addresses = []
    for iface in ("en0", "en1", "en2"):
        try:
            ip = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True).stdout.strip()
        except OSError:
            ip = ""
        if ip:
            addresses.append(ip)
    return addresses


if __name__ == "__main__":
    import uvicorn

    print()
    if not BASE_URL.startswith("http://localhost"):
        print(f"  Public:   {BASE_URL}")
    print("  Local:    http://localhost:8000")
    for ip in local_addresses():
        print(f"  Network:  http://{ip}:8000")
    print()

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, timeout_graceful_shutdown=3)
