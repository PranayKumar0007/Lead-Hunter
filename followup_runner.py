"""
followup_runner.py — Daily follow-up scheduler & dispatcher
============================================================
Run this daily at 9 AM via Windows Task Scheduler.

Scans lead_db.json for leads due for their next follow-up step,
generates AI-personalized emails, and sends them via Zoho SMTP.

Sequence timing (configurable in .env):
  Step 1 — Day  3 after initial email  (status: sent        → follow_up_1)
  Step 2 — Day  7 after initial email  (status: follow_up_1 → follow_up_2)
  Step 3 — Day 14 after initial email  (status: follow_up_2 → follow_up_3)
  Step 4 — Day 21 after initial email  (status: follow_up_3 → closing)

After closing, leads are left in "closing" status until manually marked as
replied / booked / dead via the tracker CLI.

Usage:
  python followup_runner.py          # dry run — prints actions, sends nothing
  python followup_runner.py --send   # live send via Zoho SMTP
"""

import sys
import os
import time
import random
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ── Pipeline imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lead_tracker import get_leads_due_for_followup, mark_followup_sent
from follow_up_writer import generate_followup_email, STEP_LABELS
from email_sender import send_email

# ── Config ────────────────────────────────────────────────────────────────────
ACTUALLY_SEND = (
    "--send" in sys.argv
    or os.getenv("FOLLOWUP_SEND", "False").lower() == "true"
)
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS_PER_RUN", 20))

# Maps step number → the outreach_status assigned after sending
STEP_TO_STATUS = {
    1: "follow_up_1",
    2: "follow_up_2",
    3: "follow_up_3",
    4: "closing",
}


# ── Runner ────────────────────────────────────────────────────────────────────

def run_followup_pass() -> None:
    print("\n" + "=" * 50)
    print("   📬 LEAD HUNTER — FOLLOW-UP RUNNER")
    print("=" * 50)
    print(f"   Date: {date.today()}  |  Mode: {'LIVE 🔴' if ACTUALLY_SEND else 'DRY RUN ⚪'}")
    print("=" * 50 + "\n")

    if not ACTUALLY_SEND:
        print("⚠️  DRY RUN — no emails will be sent.")
        print("   Run with --send flag to go live.\n")

    # ── Discover due leads ────────────────────────────────────────────────────
    due_leads = get_leads_due_for_followup()

    if not due_leads:
        print("✅ No leads are due for follow-up today. Check back tomorrow.\n")
        return

    print(f"📋 {len(due_leads)} lead(s) due for follow-up:\n")
    for domain, record, step in due_leads:
        print(f"   • {record.get('name', domain):<35} → Step {step}: {STEP_LABELS[step]}")
    print()

    # ── Send loop ─────────────────────────────────────────────────────────────
    results = {"sent": [], "dry_run": [], "failed": [], "skipped": []}
    sent_count = 0

    for domain, record, step in due_leads:
        if sent_count >= MAX_FOLLOWUPS:
            print(f"[FollowUp] ⛔ Reached limit of {MAX_FOLLOWUPS} emails for this run.")
            break

        name = record.get("name", domain)
        email = record.get("email", "")

        if not email:
            print(f"[FollowUp] ⏭️  No email address for '{name}' — skipping.")
            results["skipped"].append(name)
            continue

        # Generate email via GPT
        print(f"[FollowUp] 🔧 Generating Step {step} ({STEP_LABELS[step]}) for: {name}")
        email_content = generate_followup_email(record, step)

        if not email_content or not email_content.get("body"):
            print(f"[FollowUp] ❌ Could not generate email for '{name}'. Skipping.\n")
            results["failed"].append(name)
            continue

        subject = email_content["subject"]
        body    = email_content["body"]
        print(f"[FollowUp] Subject: {subject}")

        if not ACTUALLY_SEND:
            # Dry run — log but don't send or commit to DB
            print(f"[DRY RUN] Would send Step {step} to {email} ({name})\n")
            results["dry_run"].append(name)
            sent_count += 1
        else:
            success = send_email(email, subject, body)
            if success:
                mark_followup_sent(domain, step)
                results["sent"].append(name)
                sent_count += 1
                delay = random.randint(6, 15)
                print(f"[FollowUp] ⏳ Waiting {delay}s before next send...\n")
                time.sleep(delay)
            else:
                print(f"[FollowUp] ❌ Failed to send to {email}.\n")
                results["failed"].append(name)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("   FOLLOW-UP RUNNER — RUN SUMMARY")
    print("=" * 50)
    if ACTUALLY_SEND:
        print(f"  Sent (live)   : {len(results['sent'])}")
        for name in results["sent"]:
            print(f"    ✅ {name}")
    else:
        print(f"  Dry run       : {len(results['dry_run'])}")
        for name in results["dry_run"]:
            print(f"    📋 {name}")
    if results["failed"]:
        print(f"  Failed        : {len(results['failed'])}")
        for name in results["failed"]:
            print(f"    ❌ {name}")
    if results["skipped"]:
        print(f"  Skipped       : {len(results['skipped'])}")
    print("=" * 50 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_followup_pass()
