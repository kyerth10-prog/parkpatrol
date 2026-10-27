"""Spot-availability notification demo."""
import os
import random
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SERVER = os.environ.get("TRACKER_SERVER_URL", "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": os.environ["TRACKER_API_KEY"]}
SPOT_IDS = [f"A{i}" for i in range(1, 7)]
COUNTDOWN = 5

with httpx.Client(headers=HEADERS, timeout=10) as client:
    try:
        client.get(f"{SERVER}/api/spots")
    except httpx.HTTPError:
        raise SystemExit(f"Server unreachable at {SERVER}")

    # Fill the lot
    print("Marking all spots as occupied...")
    for spot_id in SPOT_IDS:
        client.post(f"{SERVER}/api/status", json={"spot_id": spot_id, "status": "OCCUPIED"})

    for seconds in range(COUNTDOWN, 0, -1):
        print(f"  Lot full. Releasing a spot in {seconds}...", end="\r")
        time.sleep(1)

    # Release one spot
    spot = random.choice(SPOT_IDS)
    client.post(f"{SERVER}/api/status", json={"spot_id": spot, "status": "VACANT"})
    print(f"\nSpot {spot} released.")
