#!/usr/bin/env python3
"""
Fetches current live and today's upcoming Soccer v4 matches and writes them
to data/live_matches.json for the web UI to consume.
"""
import os
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ["SR_API_KEY"]
BASE_URL = "https://api.sportradar.us/soccer-extended/production/v4/en"

# World Cup 2026 season ID
WC_SEASON_ID = "sr:season:101177"

LIVE_STATUSES = {"live", "inprogress"}
NOT_STARTED_STATUSES = {"not_started", "created", "scheduled"}


def fetch(path: str) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", params={"api_key": API_KEY}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    Path("data").mkdir(exist_ok=True)

    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "live": [],
        "upcoming_today": [],
    }

    try:
        data = fetch(f"/seasons/{WC_SEASON_ID}/schedules.json")
        schedules = data.get("schedules", [])

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for entry in schedules:
            status = entry.get("sport_event_status", {}).get("status", "")
            start_time = entry.get("sport_event", {}).get("start_time", "")

            if status in LIVE_STATUSES:
                result["live"].append(entry)
            elif status in NOT_STARTED_STATUSES and start_time.startswith(today):
                result["upcoming_today"].append(entry)

        print(f"Live matches: {len(result['live'])}")
        print(f"Upcoming today: {len(result['upcoming_today'])}")
    except Exception as e:
        print(f"Schedule fetch failed: {e}")

    Path("data/live_matches.json").write_text(json.dumps(result, indent=2))
    print("Written: data/live_matches.json")


if __name__ == "__main__":
    main()
