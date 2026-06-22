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
BASE_URL = "https://api.sportradar.com/soccer/extended/v4/en"

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
        live_data = fetch("/schedules/live/schedule.json")
        result["live"] = live_data.get("sport_events", [])
        print(f"Live matches: {len(result['live'])}")
    except Exception as e:
        print(f"Live schedule fetch failed: {e}")

    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_data = fetch(f"/schedules/{today}/schedule.json")
        all_today = today_data.get("sport_events", [])
        result["upcoming_today"] = [
            e for e in all_today
            if e.get("sport_event_status", {}).get("status") in NOT_STARTED_STATUSES
        ]
        print(f"Upcoming today: {len(result['upcoming_today'])}")
    except Exception as e:
        print(f"Today schedule fetch failed: {e}")

    Path("data/live_matches.json").write_text(json.dumps(result, indent=2))
    print("Written: data/live_matches.json")


if __name__ == "__main__":
    main()
