"""
snov_tracker.py - Tracks Snov.io credit usage locally to minimize API waste.
"""
import os
import json
from datetime import date

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TRACKER_FILE = os.path.join(OUTPUT_DIR, "snov_tracker.json")
STARTING_CREDITS = 50

def load_snov_tracker() -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(TRACKER_FILE):
        return {
            "credits_total": STARTING_CREDITS,
            "credits_used": 0,
            "emails_found": 0,
            "last_updated": str(date.today())
        }
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, IOError):
        print("⚠️ Failed to load snov_tracker.json. Using zeroes.")
        return {
            "credits_total": STARTING_CREDITS,
            "credits_used": 0,
            "emails_found": 0,
            "last_updated": str(date.today())
        }

def save_snov_tracker(data: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    data["last_updated"] = str(date.today())
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def can_use_snov() -> bool:
    data = load_snov_tracker()
    return data.get("credits_used", 0) < data.get("credits_total", STARTING_CREDITS)

def increment_snov_usage() -> None:
    data = load_snov_tracker()
    data["credits_used"] = data.get("credits_used", 0) + 1
    data["emails_found"] = data.get("emails_found", 0) + 1
    save_snov_tracker(data)

def print_snov_status() -> None:
    data = load_snov_tracker()
    used = data.get("credits_used", 0)
    total = data.get("credits_total", STARTING_CREDITS)
    found = data.get("emails_found", 0)
    remaining = total - used
    
    print("\n" + "-" * 20)
    print("--- SNOV STATUS ---")
    print(f"Credits Used: {used} / {total}")
    print(f"Credits Remaining: {remaining}")
    if used > 0:
        efficiency = (found / used) * 100
        print(f"Efficiency: {efficiency:.1f}% ({found} emails from {used} credits)")
    else:
        print("Efficiency: N/A (0 used)")
    print("-" * 20 + "\n")
    
    if remaining < 10:
        print("🚨 WARNING: Snov.io credits are running low (< 10 remaining) 🚨\n")
