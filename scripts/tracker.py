"""Park Patrol tracker: detects cars in Lot A and reports them to the website.

  python scripts/tracker.py --calibrate   one-time setup: click the parking corners,
                                          then save an empty-lot snapshot
  python scripts/tracker.py               run detection, report spots, upload video
  python scripts/tracker.py --show        same, with a live window showing scores
  python scripts/tracker.py --list        list cameras

The video sent to the website has the detected spots drawn on it
(set CAMERA_OVERLAY=false in .env to send the plain picture).
"""
import os
import queue
import sys
import threading
import time

import cv2
import requests

from camera import (API_KEY, BLANK_HINT, CAMERA_SOURCE, SERVER, TARGET_FPS, FrameReader,
                    encode, is_blank, list_cameras)
from detection import (BAYS, REGIONS, VIOLATION, Calibration, Detector, draw, load_empty,
                       save_empty)

DETECT_FPS = 6
STABLE_SECONDS = float(os.environ.get("TRACKER_STABLE_SECONDS", "1.5"))
RESYNC_SECONDS = 60
OVERLAY = os.environ.get("CAMERA_OVERLAY", "true").lower() != "false"

CLICK_ORDER = ["A1 end, road side", "A1 end, back", "A6 end, back", "A6 end, road side"]


# ----------------------------------------------------------------------------
# Calibration window
# ----------------------------------------------------------------------------
def calibrate():
    reader = FrameReader(CAMERA_SOURCE)
    old = Calibration.load()
    points = [tuple(map(int, p)) for p in old.corners] if old else []
    window = "Park Patrol - calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, lambda event, x, y, *_: (
        points.append((x, y)) if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4 else None))

    print("Click the 4 corners of the covered parking, in this order:")
    for i, name in enumerate(CLICK_ORDER, 1):
        print(f"  {i}. {name}")
    print("Keys:  E = save corners + empty-lot snapshot (remove all cars first)")
    print("       S = save corners only    R = start over    Q = quit")

    last_id, frame, message = -1, None, ""
    while True:
        latest, last_id = reader.next_frame(last_id, timeout=0.2)
        if latest is not None:
            frame = latest
        if frame is None:
            if cv2.waitKey(100) & 0xFF in (ord("q"), 27):
                break
            continue

        view = frame.copy()
        cal = Calibration(points, old.thresholds if old else None) if len(points) == 4 else None
        if cal:
            view = draw(view, cal)
            cv2.imshow("Straightened lot", cal.straighten(frame))
        for i, p in enumerate(points):
            cv2.circle(view, p, 7, (0, 215, 255), -1)
            cv2.putText(view, str(i + 1), (p[0] + 10, p[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 215, 255), 2)
        hint = f"Click {len(points) + 1}: {CLICK_ORDER[len(points)]}" if len(points) < 4 else \
            "E = save + empty snapshot   S = save corners   R = redo"
        for y, text in ((30, hint), (60, message)):
            cv2.putText(view, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(view, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(window, view)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            points.clear()
            message = ""
        if key in (ord("s"), ord("e")) and cal:
            cal.save()
            message = "Corners saved."
            if key == ord("e"):
                save_empty(cal, frame)
                message = "Corners and empty-lot snapshot saved. Press Q to finish."
            print(message)
    cv2.destroyAllWindows()


# ----------------------------------------------------------------------------
# Reporting to the website
# ----------------------------------------------------------------------------
class Reporter:
    """Sends status changes to the server in the background, retrying on failure."""

    def __init__(self):
        self.jobs = queue.Queue()
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = API_KEY
        threading.Thread(target=self._run, daemon=True).start()

    def send(self, spot_ids, status):
        self.jobs.put({"spot_ids": list(spot_ids), "status": status})

    def _run(self):
        while True:
            payload = self.jobs.get()
            while True:
                try:
                    res = self.session.post(f"{SERVER}/api/status", json=payload, timeout=10)
                    if res.status_code < 500:
                        if res.status_code != 200:
                            print(f"Status rejected ({res.status_code}): {res.text}")
                        break
                except requests.RequestException as error:
                    print(f"Server unreachable ({error}); retrying...")
                time.sleep(3)


class Uploader:
    """Uploads the newest (annotated) frame at CAMERA_FPS in the background."""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = API_KEY
        threading.Thread(target=self._run, daemon=True).start()

    def offer(self, frame):
        with self.lock:
            self.frame = frame

    def _run(self):
        interval = 1 / TARGET_FPS
        while True:
            started = time.time()
            with self.lock:
                frame, self.frame = self.frame, None
            if frame is not None:
                try:
                    res = self.session.post(f"{SERVER}/api/frame", data=encode(frame), timeout=5)
                    if res.status_code != 200:
                        print(f"Frame rejected ({res.status_code}): {res.text}")
                except requests.RequestException:
                    time.sleep(2)
            time.sleep(max(0.0, interval - (time.time() - started)))


class Debouncer:
    """Reports a bay's state only after it has held steady for STABLE_SECONDS."""

    def __init__(self, reporter):
        self.reporter = reporter
        self.committed = {}     # bay index -> (status_first, status_second)
        self.pending = {}       # bay index -> (state, first_seen)
        self.last_resync = time.time()

    def update(self, spots):
        now = time.time()
        for b, (first, second) in enumerate(BAYS):
            state = (spots[first], spots[second])
            if state == self.committed.get(b):
                self.pending.pop(b, None)
                continue
            seen = self.pending.get(b)
            if not seen or seen[0] != state:
                self.pending[b] = (state, now)
            elif now - seen[1] >= STABLE_SECONDS:
                self._commit(b, state)
        if now - self.last_resync >= RESYNC_SECONDS:
            self.last_resync = now
            for b, state in self.committed.items():
                self._send(b, state)

    def _commit(self, b, state):
        old = self.committed.get(b)
        self.committed[b] = state
        self.pending.pop(b, None)
        first, second = BAYS[b]
        if state[0] == VIOLATION:
            print(f"{first}+{second}: double parking")
        else:
            changes = [f"{s}: {st.lower()}" for s, st, prev in zip((first, second), state, old or (None, None)) if st != prev]
            print("  ".join(changes))
        self._send(b, state)

    def _send(self, b, state):
        first, second = BAYS[b]
        if state[0] == VIOLATION:
            self.reporter.send([first, second], VIOLATION)
        else:
            self.reporter.send([first], state[0])
            self.reporter.send([second], state[1])


# ----------------------------------------------------------------------------
# Detection loop
# ----------------------------------------------------------------------------
def run(show):
    cal, empty = Calibration.load(), load_empty()
    if cal is None or empty is None:
        raise SystemExit("Not calibrated yet. Run: python scripts/tracker.py --calibrate "
                         "(and press E with the lot empty)")
    detector = Detector(cal, empty)
    reporter, uploader = Reporter(), Uploader()
    debouncer = Debouncer(reporter)
    reader = FrameReader(CAMERA_SOURCE)
    print(f"Tracking Lot A -> {SERVER} (reporting changes held for {STABLE_SECONDS:g}s, video {TARGET_FPS:g} fps)")

    last_id, warned_black, interval = -1, False, 1 / DETECT_FPS
    while True:
        started = time.time()
        frame, last_id = reader.next_frame(last_id, timeout=1.0)
        if frame is None:
            if show and cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
            continue
        if is_blank(frame):
            if not warned_black:
                print(BLANK_HINT)
                warned_black = True
            continue

        result = detector.analyze(frame)
        debouncer.update(result["spots"])
        annotated = draw(frame, cal, result, show_scores=show) if (OVERLAY or show) else frame
        uploader.offer(annotated if OVERLAY else frame)

        if show:
            cv2.imshow("Park Patrol - live detection (Q to quit)", annotated)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
        time.sleep(max(0.0, interval - (time.time() - started)))
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_cameras()
    elif "--calibrate" in sys.argv:
        calibrate()
    else:
        run(show="--show" in sys.argv)
