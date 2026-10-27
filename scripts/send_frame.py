"""Camera frame uploader."""
import os
import threading
import time
from pathlib import Path

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0",
)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_KEY = os.environ["TRACKER_API_KEY"]
SERVER = os.environ.get("TRACKER_SERVER_URL", "http://localhost:8000").rstrip("/")
SERVER_URL = f"{SERVER}/api/frame"
CAMERA_SOURCE = os.environ.get("CAMERA_SOURCE", "1").strip()
TARGET_FPS = float(os.environ.get("CAMERA_FPS", "15"))

FRAME_WIDTH = int(os.environ.get("CAMERA_WIDTH", "640"))
JPEG_QUALITY = 70
RECONNECT_DELAY = 2
STALE_AFTER = 5


# ----------------------------------------------------------------------------
# Video source
# ----------------------------------------------------------------------------
def open_source(source):
    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
        if not cap.isOpened() and source != "0":
            cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class FrameReader:
    def __init__(self, source):
        self.source = source
        self.frame = None
        self.frame_id = 0
        self.updated = 0.0
        self.new_frame = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            cap = open_source(self.source)
            if not cap.isOpened():
                print(f"Source unavailable: {self.source}. Retrying...")
                time.sleep(RECONNECT_DELAY)
                continue

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"Connected to {self.source} ({width}x{height})")

            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    print("Source lost. Reconnecting...")
                    break
                with self.new_frame:
                    self.frame = frame
                    self.frame_id += 1
                    self.updated = time.time()
                    self.new_frame.notify_all()

            cap.release()
            time.sleep(RECONNECT_DELAY)

    def next_frame(self, last_id, timeout):
        with self.new_frame:
            self.new_frame.wait_for(lambda: self.frame_id != last_id, timeout=timeout)
            if time.time() - self.updated > STALE_AFTER:
                return None, self.frame_id
            return self.frame, self.frame_id


def test_frame():
    frame = np.zeros((360, FRAME_WIDTH, 3), dtype=np.uint8)
    frame[:] = (0, 0, 255)
    return frame


def encode(frame):
    height = int(frame.shape[0] * FRAME_WIDTH / frame.shape[1])
    resized = cv2.resize(frame, (FRAME_WIDTH, height), interpolation=cv2.INTER_AREA)
    _, jpg = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    return jpg.tobytes()


# ----------------------------------------------------------------------------
# Upload loop
# ----------------------------------------------------------------------------
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
    elif not warned_black and frame.max() < 10:
        print("Warning: source is returning blank frames.")
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
