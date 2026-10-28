"""Spot and car detection for the Lot A diorama.

How it works:
  1. Calibration: the four corners of the covered parking are clicked once on the
     camera image. A perspective transform straightens that area into a fixed
     rectangle, whatever angle or rotation the camera has.
  2. The rectangle is divided into the real layout: 3 bays stacked from A1/A2 at
     one end to A5/A6 at the other, each with two spots and a yellow divider line.
  3. An "empty" reference image of the straightened lot is saved once.
  4. Each frame is compared to that reference. A spot whose pixels changed enough
     holds a car. If a car covers a bay's yellow divider, it is straddling both
     spots, so the bay is reported as double parking.
"""
import json
import time

import cv2
import numpy as np

from camera import PROJECT_DIR

DATA_DIR = PROJECT_DIR / "data"
CALIBRATION_FILE = DATA_DIR / "lot_calibration.json"
EMPTY_FILE = DATA_DIR / "lot_empty.png"

RECT_W, RECT_H = 240, 720          # straightened parking area (road side on the left)
BAYS = [("A1", "A2"), ("A3", "A4"), ("A5", "A6")]
SPOT_IDS = [spot for bay in BAYS for spot in bay]

VACANT, OCCUPIED, VIOLATION = "VACANT", "OCCUPIED", "VIOLATION_DOUBLE_PARKED"

# Tunable in data/lot_calibration.json ("thresholds"); --show prints the live scores
DEFAULT_THRESHOLDS = {
    "pixel_delta": 32,        # how different a pixel must be from empty to count as changed (0-255)
    "spot": 0.18,             # share of a spot's pixels that must change to call it occupied
    "edges": 0.05,            # share of a spot covered by new outlines (catches black cars on black felt)
    "yellow_ratio": 0.45,     # divider is covered if less than this share of its yellow paint is visible
    "divider": 0.60,          # fallback when no yellow is visible in the empty snapshot: share changed
}

# Yellow divider paint in HSV
YELLOW_LOW = np.array([15, 90, 90])
YELLOW_HIGH = np.array([40, 255, 255])


def regions():
    """Spot and divider boxes in straightened coordinates: name -> (x1, y1, x2, y2)."""
    bay_h = RECT_H / len(BAYS)
    boxes = {}
    for b, (first, second) in enumerate(BAYS):
        y0 = b * bay_h
        boxes[first] = (0.06 * RECT_W, y0 + 0.08 * bay_h, 0.94 * RECT_W, y0 + 0.43 * bay_h)
        boxes[second] = (0.06 * RECT_W, y0 + 0.57 * bay_h, 0.94 * RECT_W, y0 + 0.92 * bay_h)
        boxes[f"divider{b}"] = (0.06 * RECT_W, y0 + 0.455 * bay_h, 0.80 * RECT_W, y0 + 0.545 * bay_h)
    return {name: tuple(int(round(v)) for v in box) for name, box in boxes.items()}


REGIONS = regions()


# ----------------------------------------------------------------------------
# Calibration
# ----------------------------------------------------------------------------
class Calibration:
    """The four clicked corners, in this order:
    1. A1 end, road side   2. A1 end, back   3. A6 end, back   4. A6 end, road side
    """

    def __init__(self, corners, thresholds=None):
        self.corners = np.float32(corners)
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        target = np.float32([[0, 0], [RECT_W, 0], [RECT_W, RECT_H], [0, RECT_H]])
        self.matrix = cv2.getPerspectiveTransform(self.corners, target)
        self.inverse = cv2.getPerspectiveTransform(target, self.corners)

    @classmethod
    def load(cls):
        if not CALIBRATION_FILE.exists():
            return None
        data = json.loads(CALIBRATION_FILE.read_text())
        return cls(data["corners"], data.get("thresholds"))

    def save(self):
        DATA_DIR.mkdir(exist_ok=True)
        CALIBRATION_FILE.write_text(json.dumps({
            "corners": self.corners.tolist(),
            "thresholds": self.thresholds,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2))

    def straighten(self, frame):
        return cv2.warpPerspective(frame, self.matrix, (RECT_W, RECT_H))

    def to_camera(self, box):
        """A straightened box as a polygon on the camera image."""
        x1, y1, x2, y2 = box
        points = np.float32([[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]])
        return cv2.perspectiveTransform(points, self.inverse).astype(np.int32)


def save_empty(calibration, frame):
    DATA_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(EMPTY_FILE), calibration.straighten(frame))


def load_empty():
    return cv2.imread(str(EMPTY_FILE)) if EMPTY_FILE.exists() else None


# ----------------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------------
def _prepare(image):
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    return gray, hsv


def _edges(gray):
    return cv2.Canny(gray, 30, 90)


def _share(mask, box):
    x1, y1, x2, y2 = box
    area = mask[y1:y2, x1:x2]
    return float(area.mean()) / 255 if area.size else 0.0


class Detector:
    def __init__(self, calibration, empty_image):
        self.cal = calibration
        self.ref_gray, ref_hsv = _prepare(empty_image)
        self.ref_sat = ref_hsv[:, :, 1]
        self.ref_median = max(float(np.median(self.ref_gray)), 1.0)
        ref_yellow = cv2.inRange(ref_hsv, YELLOW_LOW, YELLOW_HIGH)
        self.ref_yellow = {b: _share(ref_yellow, REGIONS[f"divider{b}"]) for b in range(len(BAYS))}
        self.kernel = np.ones((3, 3), np.uint8)
        # Outlines already in the empty lot (lines, posts, felt texture) are ignored
        self.ref_edges = cv2.dilate(_edges(self.ref_gray), np.ones((7, 7), np.uint8))

    def analyze(self, frame):
        """Spot statuses and the scores behind them for one camera frame."""
        t = self.cal.thresholds
        gray, hsv = _prepare(self.cal.straighten(frame))

        # Compensate for overall brightness changes (room lights, clouds)
        gain = np.clip(self.ref_median / max(float(np.median(gray)), 1.0), 0.6, 1.6)
        gray = cv2.convertScaleAbs(gray, alpha=gain)

        changed = ((cv2.absdiff(gray, self.ref_gray) > t["pixel_delta"]) |
                   (cv2.absdiff(hsv[:, :, 1], self.ref_sat) > t["pixel_delta"] * 1.5))
        changed = cv2.morphologyEx(changed.astype(np.uint8) * 255, cv2.MORPH_OPEN, self.kernel)
        new_edges = cv2.bitwise_and(_edges(gray), cv2.bitwise_not(self.ref_edges))
        new_edges = cv2.dilate(new_edges, self.kernel)
        yellow = cv2.inRange(hsv, YELLOW_LOW, YELLOW_HIGH)

        spots, scores, groups = {}, {}, []
        for b, (first, second) in enumerate(BAYS):
            divider = REGIONS[f"divider{b}"]
            divider_change = _share(changed, divider)
            if self.ref_yellow[b] > 0.03:
                # The yellow line is the reliable signal: a car parked inside its spot leaves
                # it visible; a car straddling the two spots hides it.
                visible_yellow = _share(yellow, divider) / self.ref_yellow[b]
                covered = visible_yellow < t["yellow_ratio"]
            else:
                visible_yellow = 1.0
                covered = divider_change > t["divider"]
            scores[f"divider{b}"] = {"change": round(divider_change, 2), "yellow": round(min(visible_yellow, 9.99), 2)}

            for spot in (first, second):
                share = _share(changed, REGIONS[spot])
                edges = _share(new_edges, REGIONS[spot])
                scores[spot] = round(max(share, edges * t["spot"] / t["edges"]), 2)
                spots[spot] = OCCUPIED if share > t["spot"] or edges > t["edges"] else VACANT
            if covered:
                spots[first] = spots[second] = VIOLATION
                groups.append([first, second])
        return {"spots": spots, "scores": scores, "groups": groups}


# ----------------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------------
COLORS = {VACANT: (74, 163, 22), OCCUPIED: (150, 150, 150), VIOLATION: (11, 138, 224)}   # BGR


def draw(frame, calibration, result=None, show_scores=False):
    """The camera frame with spot outlines, labels, and (optionally) scores."""
    out = frame.copy()
    for spot in SPOT_IDS:
        polygon = calibration.to_camera(REGIONS[spot])
        status = result["spots"][spot] if result else VACANT
        color = COLORS[status] if result else (255, 255, 255)
        overlay = out.copy()
        cv2.fillPoly(overlay, [polygon], color)
        cv2.addWeighted(overlay, 0.25, out, 0.75, 0, out)
        cv2.polylines(out, [polygon], True, color, 2, cv2.LINE_AA)
        label = spot
        if show_scores and result:
            label += f" {result['scores'][spot]:.2f}"
        x, y = polygon[:, 0, :].mean(axis=0).astype(int)
        cv2.putText(out, label, (x - 22, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, label, (x - 22, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    for b in range(len(BAYS)):
        polygon = calibration.to_camera(REGIONS[f"divider{b}"])
        covered = bool(result) and any(BAYS[b][0] in g for g in result["groups"])
        cv2.polylines(out, [polygon], True, COLORS[VIOLATION] if covered else (0, 215, 255), 1, cv2.LINE_AA)
        if show_scores and result:
            s = result["scores"][f"divider{b}"]
            x, y = polygon[:, 0, :].max(axis=0)
            cv2.putText(out, f"line {s['change']:.2f}/{s['yellow']:.2f}", (int(x) + 6, int(y)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 215, 255), 1, cv2.LINE_AA)
    return out
