"""Spot and car detection for the Lot A diorama.

How it works:
  1. Calibration: the four corners of the covered parking are clicked once on the
     camera image. A perspective transform straightens that area into a fixed
     rectangle, whatever angle or rotation the camera has.
  2. The rectangle is divided into the real layout: 3 bays stacked from A1/A2 at
     one end to A5/A6 at the other, each with two spots split by a yellow line.
     Each line's exact position is measured from the empty-lot snapshot.
  3. Each frame is compared to that empty snapshot. A spot whose pixels changed
     enough has something in it.
  4. Double parking: if something covers the strip around a bay's yellow line
     across a good part of the bay's width, one object is sitting on both spots,
     at any angle (parked across or parallel) and in any colour.
  5. Car or not: each object is compared with examples of the real toy cars (and
     of other objects) taught in the calibration window, using image features from
     a small pretrained network (MobileNetV2). Only objects that clearly match a
     taught car count; anything unfamiliar is treated as "not a car".
"""
import hashlib
import json
import time
import urllib.request

import cv2
import numpy as np

from camera import PROJECT_DIR

DATA_DIR = PROJECT_DIR / "data"
CALIBRATION_FILE = DATA_DIR / "lot_calibration.json"
EMPTY_FILE = DATA_DIR / "lot_empty.png"
EXAMPLES_FILE = DATA_DIR / "object_examples.npz"
EXAMPLES_DIR = DATA_DIR / "examples"           # thumbnails of every taught example
MODEL_FILE = DATA_DIR / "models" / "mobilenetv2-12.onnx"
MODEL_URL = ("https://media.githubusercontent.com/media/onnx/models/main/validated/"
             "vision/classification/mobilenet/model/mobilenetv2-12.onnx")
MODEL_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"
FEATURE_LAYER = "onnx_node!Reshape_103"        # 1280 image features before the classifier

RECT_W, RECT_H = 240, 720          # straightened parking area (road side on the left)
BAYS = [("A1", "A2"), ("A3", "A4"), ("A5", "A6")]
SPOT_IDS = [spot for bay in BAYS for spot in bay]
BAY_H = RECT_H / len(BAYS)

VACANT, OCCUPIED, VIOLATION = "VACANT", "OCCUPIED", "VIOLATION_DOUBLE_PARKED"
CAR, ITEM = "car", "item"

# Tunable in data/lot_calibration.json ("thresholds"); --show prints the live scores
DEFAULT_THRESHOLDS = {
    "pixel_delta": 32,        # how different a pixel must be from empty to count as changed (0-255)
    "spot": 0.18,             # share of a spot's pixels that must change to call it occupied
    "edges": 0.05,            # share of a spot covered by new outlines (catches black cars on black felt)
    "straddle": 0.20,         # share of the bay's width covered across the yellow-line strip = double parking
    "yellow_ratio": 0.45,     # also double parking if less than this share of the line's yellow is visible
    "car_match": 0.72,        # how similar (0-1) an object must be to a taught car to count as a car
}

# Half-height (pixels, straightened) of the strip checked around each painted line.
# Only things actually on the line count, so cars parked close to it are fine.
LINE_HALF = 5

# Yellow divider paint in HSV
YELLOW_LOW = np.array([15, 90, 90])
YELLOW_HIGH = np.array([40, 255, 255])


def regions(line_rows=None):
    """Spot and divider boxes in straightened coordinates: name -> (x1, y1, x2, y2).

    line_rows: the measured y of each bay's yellow line (defaults to mid-bay).
    """
    boxes = {}
    for b, (first, second) in enumerate(BAYS):
        y0, y1 = b * BAY_H, (b + 1) * BAY_H
        line = line_rows[b] if line_rows else y0 + BAY_H / 2
        boxes[first] = (0.06 * RECT_W, y0 + 0.08 * BAY_H, 0.94 * RECT_W, line - 0.04 * BAY_H)
        boxes[second] = (0.06 * RECT_W, line + 0.04 * BAY_H, 0.94 * RECT_W, y1 - 0.08 * BAY_H)
        boxes[f"divider{b}"] = (0.06 * RECT_W, line - 0.045 * BAY_H, 0.80 * RECT_W, line + 0.045 * BAY_H)
        boxes[f"bay{b}"] = (0.03 * RECT_W, y0 + 0.04 * BAY_H, 0.95 * RECT_W, y1 - 0.04 * BAY_H)
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
# Car recognition (taught with examples of the real toy cars)
# ----------------------------------------------------------------------------
def ensure_model():
    """Download the MobileNetV2 feature model once (about 14 MB), checking its fingerprint."""
    if MODEL_FILE.exists():
        return True
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading the car recognition model (about 14 MB)...")
    try:
        data = urllib.request.urlopen(MODEL_URL, timeout=120).read()
    except OSError as error:
        print("Couldn't download the model:", error)
        return False
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        print("The downloaded model didn't match its expected fingerprint; not using it.")
        return False
    MODEL_FILE.write_bytes(data)
    return True


class CarRecognizer:
    MEAN = np.array([0.485, 0.456, 0.406], np.float32)
    STD = np.array([0.229, 0.224, 0.225], np.float32)

    def __init__(self):
        self.net = cv2.dnn.readNetFromONNX(str(MODEL_FILE)) if MODEL_FILE.exists() else None
        self.vectors = np.zeros((0, 1280), np.float32)
        self.labels = np.array([], dtype="<U8")
        if EXAMPLES_FILE.exists():
            data = np.load(EXAMPLES_FILE)
            self.vectors, self.labels = data["vectors"], data["labels"]

    @property
    def taught(self):
        return self.net is not None and (self.labels == CAR).any()

    def counts(self):
        return int((self.labels == CAR).sum()), int((self.labels == ITEM).sum())

    def features(self, crop):
        img = cv2.cvtColor(cv2.resize(crop, (224, 224)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        self.net.setInput(((img - self.MEAN) / self.STD).transpose(2, 0, 1)[None])
        v = self.net.forward(FEATURE_LAYER).reshape(-1).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def add(self, crop, label):
        self.vectors = np.vstack([self.vectors, self.features(crop)[None]])
        self.labels = np.append(self.labels, label)
        np.savez(EXAMPLES_FILE, vectors=self.vectors, labels=self.labels)
        EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(EXAMPLES_DIR / f"{label}-{len(self.labels):04d}.png"), crop)

    def forget(self):
        self.vectors = np.zeros((0, 1280), np.float32)
        self.labels = np.array([], dtype="<U8")
        EXAMPLES_FILE.unlink(missing_ok=True)
        for f in EXAMPLES_DIR.glob("*.png"):
            f.unlink()

    def classify(self, crop, threshold, margin=0.03):
        """(CAR or ITEM, similarity to the closest taught car).

        A car must be similar enough to one of the taught cars AND clearly closer to the
        cars than to any taught non-car object. Anything unfamiliar is treated as an item.
        """
        v = self.features(crop)
        sims = self.vectors @ v
        car_sim = float(sims[self.labels == CAR].max())
        item_sim = float(sims[self.labels == ITEM].max()) if (self.labels == ITEM).any() else 0.0
        return (CAR if car_sim >= threshold and car_sim >= item_sim + margin else ITEM), car_sim


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


def _crop(image, box):
    x1, y1, x2, y2 = box
    return image[y1:y2, x1:x2]


def _longest_run(flags):
    best = run = 0
    for v in flags:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


class Detector:
    def __init__(self, calibration, empty_image, recognizer=None):
        self.cal = calibration
        self.recognizer = recognizer
        self.ref_gray, ref_hsv = _prepare(empty_image)
        self.ref_sat = ref_hsv[:, :, 1]
        self.ref_median = max(float(np.median(self.ref_gray)), 1.0)
        self.kernel = np.ones((3, 3), np.uint8)
        # Outlines already in the empty lot (lines, posts, felt texture) are ignored
        self.ref_edges = cv2.dilate(_edges(self.ref_gray), np.ones((7, 7), np.uint8))

        # Where each yellow line really is (lines are rarely exactly mid-bay)
        ref_yellow = cv2.inRange(ref_hsv, YELLOW_LOW, YELLOW_HIGH)
        self.line_rows = []
        for b in range(len(BAYS)):
            lo, hi = int(b * BAY_H + 0.3 * BAY_H), int(b * BAY_H + 0.7 * BAY_H)
            rows = ref_yellow[lo:hi].sum(axis=1) / 255
            found = rows.max() > 0.05 * RECT_W
            self.line_rows.append(lo + int(np.argmax(rows)) if found else int(b * BAY_H + BAY_H / 2))
        self.regions = regions(self.line_rows)
        self.ref_yellow = {b: _share(ref_yellow, self.regions[f"divider{b}"]) for b in range(len(BAYS))}
        self._cache = {}

    # -- what's in the picture ----------------------------------------------
    @staticmethod
    def _line_cover(present, line):
        """Longest stretch of the painted line (as a share of the bay's width) with something on it."""
        band = present[max(0, line - LINE_HALF):line + LINE_HALF + 1, int(0.03 * RECT_W):int(0.93 * RECT_W)]
        return _longest_run(band.max(axis=0) > 0) / RECT_W

    def _masks(self, straight):
        t = self.cal.thresholds
        gray, hsv = _prepare(straight)
        # Compensate for overall brightness changes (room lights, clouds)
        gain = np.clip(self.ref_median / max(float(np.median(gray)), 1.0), 0.6, 1.6)
        gray = cv2.convertScaleAbs(gray, alpha=gain)
        changed = ((cv2.absdiff(gray, self.ref_gray) > t["pixel_delta"]) |
                   (cv2.absdiff(hsv[:, :, 1], self.ref_sat) > t["pixel_delta"] * 1.5))
        changed = cv2.morphologyEx(changed.astype(np.uint8) * 255, cv2.MORPH_OPEN, self.kernel)
        new_edges = cv2.dilate(cv2.bitwise_and(_edges(gray), cv2.bitwise_not(self.ref_edges)), self.kernel)
        yellow = cv2.inRange(hsv, YELLOW_LOW, YELLOW_HIGH)
        return changed, new_edges, yellow

    def _kind(self, key, straight, mask, box):
        """CAR or ITEM for the object in `box`, re-checked only when the object changes."""
        if not (self.recognizer and self.recognizer.taught):
            return CAR, None                      # not taught yet: anything counts as a car
        small = cv2.resize(_crop(mask, box), (24, 12), interpolation=cv2.INTER_AREA) > 64
        cached = self._cache.get(key)
        if cached:
            union = (small | cached[0]).sum()
            same = union == 0 or (small & cached[0]).sum() / union > 0.7
            if same and time.time() - cached[3] < 10:
                return cached[1], cached[2]
        kind, sim = self.recognizer.classify(_crop(straight, box), self.cal.thresholds["car_match"])
        self._cache[key] = (small, kind, sim, time.time())
        return kind, sim

    def analyze(self, frame):
        """Spot statuses and the scores behind them for one camera frame."""
        t = self.cal.thresholds
        straight = self.cal.straighten(frame)
        changed, new_edges, yellow = self._masks(straight)
        present = cv2.bitwise_or(changed, new_edges)

        spots, scores, groups, kinds = {}, {}, [], {}
        for b, (first, second) in enumerate(BAYS):
            line = self.line_rows[b]
            # Double parking: something covers the strip around the yellow line across the bay
            cover = self._line_cover(present, line)
            visible = (_share(yellow, self.regions[f"divider{b}"]) / self.ref_yellow[b]) if self.ref_yellow[b] > 0.03 else 1.0
            straddle = cover >= t["straddle"] or visible < t["yellow_ratio"]
            scores[f"divider{b}"] = {"cover": round(cover, 2), "yellow": round(min(visible, 9.99), 2)}

            occupied = {}
            for spot in (first, second):
                share = _share(changed, self.regions[spot])
                edges = _share(new_edges, self.regions[spot])
                scores[spot] = round(max(share, edges * t["spot"] / t["edges"]), 2)
                occupied[spot] = share > t["spot"] or edges > t["edges"]

            if straddle:
                kind, sim = self._kind(f"bay{b}", straight, present, self.regions[f"bay{b}"])
                kinds[first] = kinds[second] = (kind, sim)
                if kind == CAR:
                    spots[first] = spots[second] = VIOLATION
                    groups.append([first, second])
                    continue
                # A non-car object across the line blocks nothing
                spots[first] = spots[second] = VACANT
                continue
            for spot in (first, second):
                if not occupied[spot]:
                    spots[spot] = VACANT
                    continue
                kind, sim = self._kind(spot, straight, present, self.regions[spot])
                kinds[spot] = (kind, sim)
                spots[spot] = OCCUPIED if kind == CAR else VACANT
        items = [s for s, (k, _) in kinds.items() if k == ITEM]
        return {"spots": spots, "scores": scores, "groups": groups, "kinds": kinds, "items": items,
                "regions": self.regions}

    # -- teaching -------------------------------------------------------------
    def teach(self, frame, label):
        """Save every object currently in the lot as an example of `label` (CAR or ITEM)."""
        if not self.recognizer or self.recognizer.net is None:
            return 0
        t = self.cal.thresholds
        straight = self.cal.straighten(frame)
        changed, new_edges, _ = self._masks(straight)
        present = cv2.bitwise_or(changed, new_edges)
        saved = 0
        for b, (first, second) in enumerate(BAYS):
            line = self.line_rows[b]
            if self._line_cover(present, line) >= t["straddle"]:
                self.recognizer.add(_crop(straight, self.regions[f"bay{b}"]), label)
                saved += 1
                continue
            for spot in (first, second):
                share = _share(changed, self.regions[spot])
                edges = _share(new_edges, self.regions[spot])
                if share > t["spot"] or edges > t["edges"]:
                    self.recognizer.add(_crop(straight, self.regions[spot]), label)
                    saved += 1
        self._cache.clear()
        return saved


# ----------------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------------
COLORS = {VACANT: (74, 163, 22), OCCUPIED: (150, 150, 150), VIOLATION: (11, 138, 224)}   # BGR
ITEM_COLOR = (235, 235, 235)


def draw(frame, calibration, result=None, show_scores=False):
    """The camera frame with spot outlines, labels, and (optionally) scores."""
    out = frame.copy()
    boxes = result["regions"] if result else REGIONS
    for spot in SPOT_IDS:
        polygon = calibration.to_camera(boxes[spot])
        status = result["spots"][spot] if result else VACANT
        is_item = bool(result) and spot in result["items"]
        color = ITEM_COLOR if is_item else COLORS[status] if result else (255, 255, 255)
        overlay = out.copy()
        cv2.fillPoly(overlay, [polygon], color)
        cv2.addWeighted(overlay, 0.25, out, 0.75, 0, out)
        cv2.polylines(out, [polygon], True, color, 2, cv2.LINE_AA)
        label = spot + (" item" if is_item else "")
        if show_scores and result:
            label += f" {result['scores'][spot]:.2f}"
            sim = result["kinds"].get(spot, (None, None))[1]
            if sim is not None:
                label += f" car~{sim:.2f}"
        x, y = polygon[:, 0, :].mean(axis=0).astype(int)
        cv2.putText(out, label, (x - 30, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, label, (x - 30, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    for b in range(len(BAYS)):
        polygon = calibration.to_camera(boxes[f"divider{b}"])
        covered = bool(result) and any(BAYS[b][0] in g for g in result["groups"])
        cv2.polylines(out, [polygon], True, COLORS[VIOLATION] if covered else (0, 215, 255), 1, cv2.LINE_AA)
        if show_scores and result:
            s = result["scores"][f"divider{b}"]
            x, y = polygon[:, 0, :].max(axis=0)
            cv2.putText(out, f"line {s['cover']:.2f}/{s['yellow']:.2f}", (int(x) + 6, int(y)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 215, 255), 1, cv2.LINE_AA)
    return out
