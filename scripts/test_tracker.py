"""Tracker simulator."""
import os
import random
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SERVER = os.environ.get("TRACKER_SERVER_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ["TRACKER_API_KEY"]
STATUSES = ["VACANT", "OCCUPIED", "OCCUPIED", "VIOLATION_DOUBLE_PARKED"]
INTERVAL = 1.5
STRADDLE_CHANCE = 0.15

# Three covered bays of two spots; a car can straddle the two spots in one bay
ROWS = [["A1", "A2"], ["A3", "A4"], ["A5", "A6"]]
SPOT_IDS = [spot for row in ROWS for spot in row]
ADJACENT_PAIRS = [row[i:i + 2] for row in ROWS for i in range(len(row) - 1)]


def next_update():
    if random.random() < STRADDLE_CHANCE:
        pair = random.choice(ADJACENT_PAIRS)
        status = random.choice(["VIOLATION_DOUBLE_PARKED", "VACANT"])
        return {"spot_ids": pair, "status": status}
    return {"spot_id": random.choice(SPOT_IDS), "status": random.choice(STATUSES)}


print(f"Sending simulated statuses to {SERVER}")
with httpx.Client(headers={"X-API-Key": API_KEY}, timeout=5) as client:
    while True:
        update = next_update()
        try:
            response = client.post(f"{SERVER}/api/status", json=update)
            print(update.get("spot_ids") or update["spot_id"], update["status"], response.status_code)
        except httpx.HTTPError as error:
            print("Server unreachable:", error)
        time.sleep(INTERVAL)
