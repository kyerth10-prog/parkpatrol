"""Camera frame uploader (video only, no detection).

For spot detection use scripts/tracker.py, which also uploads the video.
See scripts/camera.py for the CAMERA_SOURCE options.
"""
import sys
import time

import requests

from camera import (API_KEY, BLANK_HINT, CAMERA_SOURCE, SERVER, TARGET_FPS, FrameReader,
                    encode, is_blank, list_cameras, test_frame)

SERVER_URL = f"{SERVER}/api/frame"

if "--list" in sys.argv:
    list_cameras()
    raise SystemExit

reader = FrameReader(CAMERA_SOURCE)
session = requests.Session()
session.headers["X-API-Key"] = API_KEY
interval = 1 / TARGET_FPS
print(f"Sending frames to {SERVER_URL} (up to {TARGET_FPS:g} fps)")

last_id, warned_black = -1, False
sent, window_start = 0, time.time()
while True:
    started = time.time()
    frame, last_id = reader.next_frame(last_id, timeout=1.0)
    if frame is None:
        frame = test_frame()
    elif not warned_black and is_blank(frame):
        print(BLANK_HINT)
        warned_black = True

    try:
        res = session.post(SERVER_URL, data=encode(frame), timeout=5)
        if res.status_code != 200:
            print(f"Server Response: {res.status_code} -> {res.text}")
        sent += 1
    except requests.RequestException as e:
        print(f"Server unreachable: {e}")
        time.sleep(2)

    if time.time() - window_start >= 10:
        print(f"Uploading at {sent / (time.time() - window_start):.1f} fps")
        sent, window_start = 0, time.time()

    time.sleep(max(0.0, interval - (time.time() - started)))
