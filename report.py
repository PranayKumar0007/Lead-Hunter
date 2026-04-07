import csv
import os
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FIELDS = [
    "name",
    "address",
    "phone",
    "website",
    "email",
    "email_source",
    "email_subject",
    "email_body",
    "send_status",
]


def save_to_csv(leads: list[dict], filename: str = "leads.csv") -> str:
    """
    Save leads list to CSV file in the output/ directory.
    Returns the full path to the saved file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    print(f"[Report] Saved {len(leads)} leads to {filepath}")
    return filepath


def print_summary(leads: list[dict]) -> None:
    """Print a quick console summary of the pipeline results."""
    total = len(leads)
    with_email = sum(1 for l in leads if l.get("email"))
    with_body = sum(1 for l in leads if l.get("email_body"))
    sent = sum(1 for l in leads if l.get("send_status") == "sent")
    dry_run = sum(1 for l in leads if l.get("send_status") == "dry_run")
    skipped = sum(1 for l in leads if l.get("send_status") == "skipped")
    guessed = sum(1 for l in leads if l.get("email_details", {}).get("source") == "Pattern Guessing")

    print("\n" + "=" * 42)
    print("       LEAD HUNTER — RUN SUMMARY")
    print("=" * 42)
    print(f"  Total businesses found : {total}")
    print(f"  Emails found           : {with_email}")
    print(f"  Emails generated (AI)  : {with_body}")
    print(f"  Sent (live)            : {sent}")
    print(f"  Dry run (not sent)     : {dry_run}")
    print(f"  Skipped (no email)     : {skipped}")
    print(f"  Guessed (skipped)      : {guessed}")
    print("=" * 42 + "\n")
