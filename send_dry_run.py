"""
send_dry_run.py — Send pending cold emails from output/leads.csv
================================================================
Reads leads.csv, sends ONLY rows where send_status == "dry_run"
(and email / subject / body are all present), updates statuses
to "sent" or "failed", and overwrites the CSV in place.

Usage:
    python send_dry_run.py
"""

import csv
import os
import time

from email_sender import send_email

CSV_PATH = os.path.join(os.path.dirname(__file__), "output", "leads.csv")
DELAY_SECONDS = 20


# ── helpers ────────────────────────────────────────────────────────────────────

def load_leads(filepath: str) -> list[dict]:
    """Read every row from the leads CSV into a list of dicts."""
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_leads(filepath: str, leads: list[dict]) -> None:
    """Overwrite the CSV with the (possibly updated) leads list."""
    if not leads:
        return
    fieldnames = leads[0].keys()
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def is_sendable(lead: dict) -> bool:
    """Return True only if this lead is a valid dry-run candidate."""
    return (
        lead.get("send_status", "").strip() == "dry_run"
        and lead.get("email", "").strip()
        and lead.get("email_subject", "").strip()
        and lead.get("email_body", "").strip()
    )


# ── main logic ─────────────────────────────────────────────────────────────────

def run() -> None:
    if not os.path.exists(CSV_PATH):
        print(f"[Error] CSV not found: {CSV_PATH}")
        return

    leads = load_leads(CSV_PATH)
    if not leads:
        print("[Info] leads.csv is empty — nothing to do.")
        return

    sendable = [l for l in leads if is_sendable(l)]
    total = len(leads)
    pending = len(sendable)

    if pending == 0:
        print(f"[Info] No dry_run leads to send ({total} total rows in CSV).")
        return

    print(f"\n📨  Found {pending} pending email(s) out of {total} total leads.\n")

    sent_count = 0
    failed_count = 0

    for idx, lead in enumerate(sendable, start=1):
        name = lead.get("name", "unknown")
        email = lead["email"].strip()
        subject = lead["email_subject"].strip()
        body = lead["email_body"].strip()

        print(f"[{idx}/{pending}] Sending to {name} <{email}>...")

        try:
            success = send_email(email, subject, body)
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            success = False

        if success:
            lead["send_status"] = "sent"
            sent_count += 1
            print(f"  ✓ Sent successfully.")
        else:
            lead["send_status"] = "failed"
            failed_count += 1
            print(f"  ✗ Failed to send.")

        # Anti-spam delay (skip after the last email)
        if idx < pending:
            print(f"  ⏳ Waiting {DELAY_SECONDS}s before next email...")
            time.sleep(DELAY_SECONDS)

    # Save updated statuses back to CSV
    save_leads(CSV_PATH, leads)
    print(f"\n[Report] CSV updated: {CSV_PATH}")

    # Summary
    skipped = total - pending
    print("\n" + "=" * 40)
    print("   SEND DRY-RUN — SUMMARY")
    print("=" * 40)
    print(f"  Total rows in CSV  : {total}")
    print(f"  Pending (dry_run)  : {pending}")
    print(f"  Sent               : {sent_count}")
    print(f"  Failed             : {failed_count}")
    print(f"  Skipped            : {skipped}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    run()
