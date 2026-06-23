#!/usr/bin/env python3
"""
Records timestamped snapshots of Soccer v4 extended API endpoints during a live match.
Polls at a configurable interval and stops automatically when the match ends.
"""
import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ["SR_API_KEY"]
BASE_URL = "https://api.sportradar.us/soccer-extended/production/v4/en"

ENDPOINTS = {
    "summary": "/sport_events/{match_id}/summary.json",
    "timeline": "/sport_events/{match_id}/timeline.json",
    "extended_summary": "/sport_events/{match_id}/extended_summary.json",
    "extended_timeline": "/sport_events/{match_id}/extended_timeline.json",
}

TERMINAL_STATUSES = {"closed", "ended", "postponed", "cancelled", "abandoned"}


def fetch_endpoint(match_id: str, endpoint_name: str) -> dict:
    path = ENDPOINTS[endpoint_name].format(match_id=match_id)
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params={"api_key": API_KEY}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_match_status(match_id: str) -> str:
    try:
        data = fetch_endpoint(match_id, "summary")
        return data.get("sport_event_status", {}).get("status", "unknown")
    except Exception as e:
        print(f"  Warning: could not fetch match status: {e}")
        return "unknown"


def save_snapshot(match_id: str, endpoint_name: str, data: dict, snapshot_dir: Path):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = snapshot_dir / match_id.replace(":", "_") / endpoint_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ts}.json"
    out_file.write_text(json.dumps(data, indent=2))
    print(f"    saved {out_file.name}")


def git_commit(match_id: str):
    import subprocess
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    result = subprocess.run(
        ["git", "add", "snapshots/"],
        capture_output=True, text=True
    )
    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"snapshots: {match_id} {ts}"], check=True)
        subprocess.run(["git", "pull", "--rebase"], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"  [git] committed and pushed at {ts}")
    else:
        print(f"  [git] nothing new to commit")


def poll_once(match_id: str, endpoints: list, snapshot_dir: Path):
    for ep in endpoints:
        try:
            data = fetch_endpoint(match_id, ep)
            save_snapshot(match_id, ep, data, snapshot_dir)
        except requests.HTTPError as e:
            print(f"    HTTP {e.response.status_code} on {ep}")
        except Exception as e:
            print(f"    error on {ep}: {e}")
        time.sleep(1)  # Respect rate limit: 1 req/sec


def main():
    parser = argparse.ArgumentParser(description="Record SR API snapshots for a live match")
    parser.add_argument("match_id", help="e.g. sr:sport_event:12345678")
    parser.add_argument(
        "--endpoints",
        default="summary,timeline,extended_summary,extended_timeline",
        help="Comma-separated list of endpoints to capture",
    )
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    parser.add_argument("--max-duration", type=int, default=10800, help="Max recording time in seconds (default: 10800 = 3h)")
    parser.add_argument("--commit-every", type=int, default=5, help="Commit snapshots to git every N polls (default: 5)")
    args = parser.parse_args()

    match_id = args.match_id
    endpoints = [e.strip() for e in args.endpoints.split(",") if e.strip() in ENDPOINTS]

    if not endpoints:
        print(f"No valid endpoints specified. Available: {', '.join(ENDPOINTS)}")
        sys.exit(1)

    snapshot_dir = Path("snapshots") / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print(f"Match:     {match_id}")
    print(f"Endpoints: {', '.join(endpoints)}")
    print(f"Interval:  {args.interval}s  |  Max duration: {args.max_duration}s")
    print(f"Output:    {snapshot_dir}/")
    print()

    start = time.time()
    poll_count = 0

    while time.time() - start < args.max_duration:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        status = get_match_status(match_id)
        poll_count += 1
        print(f"[{now}] poll #{poll_count}  status={status}")

        poll_once(match_id, endpoints, snapshot_dir)

        if poll_count % args.commit_every == 0 or status in TERMINAL_STATUSES:
            git_commit(match_id)

        if status in TERMINAL_STATUSES:
            print(f"\nMatch reached terminal status '{status}'. Recording complete.")
            print(f"Total polls: {poll_count}")
            break

        elapsed = time.time() - start
        sleep_time = max(0, args.interval - len(endpoints))
        if elapsed + sleep_time < args.max_duration:
            time.sleep(sleep_time)
    else:
        git_commit(match_id)
        print(f"\nMax duration reached ({args.max_duration}s). Stopping.")


if __name__ == "__main__":
    main()
