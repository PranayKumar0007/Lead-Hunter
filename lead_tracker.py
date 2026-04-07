"""
lead_tracker.py — Persistent lead database for Lead Hunter
============================================================
Stores all leads across runs in output/lead_db.json.
Keys leads by domain so duplicates are never counted twice.

Full lifecycle status model:
  pending      — found, not yet emailed
  sent         — initial cold email sent        (Day 0)
  follow_up_1  — first follow-up sent           (Day 3)
  follow_up_2  — second follow-up sent          (Day 7)
  follow_up_3  — third follow-up sent           (Day 14)
  closing      — closing / call-invite sent     (Day 21)
  replied      — lead replied (manually marked)
  booked       — call booked (manually marked)
  closed       — deal closed (manually marked)
  dead         — no response, removed from seq  (manually marked)
  skipped      — no email address / opted out
"""

import json
import os
from datetime import date
from urllib.parse import urlparse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
DB_FILE = os.path.join(OUTPUT_DIR, "lead_db.json")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _domain_from_lead(lead: dict) -> str:
    """Return a clean domain key from a lead dict."""
    website = lead.get("website", "") or lead.get("email", "")
    if "@" in website:
        # extract domain from email
        return website.split("@")[-1].lower().strip()
    parsed = urlparse(website if website.startswith("http") else f"https://{website}")
    return parsed.netloc.replace("www.", "").lower().strip()


def _send_status_to_outreach(send_status: str) -> str:
    """Map pipeline send_status values to tracker outreach_status values."""
    mapping = {
        "sent":     "sent",
        "dry_run":  "pending",
        "skipped":  "skipped",
        "failed":   "pending",
    }
    return mapping.get(send_status, "pending")


# ── Core DB operations ────────────────────────────────────────────────────────

def load_db() -> dict:
    """Load the lead database from disk. Returns empty dict if first run."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print("[Tracker] ⚠️ Could not read lead_db.json — starting fresh.")
        return {}


def save_db(db: dict) -> None:
    """Write the lead database back to disk."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def get_known_domains() -> set:
    """
    Return all domains currently in the database to ensure
    Google Maps fetching skips them and finds fresh leads.
    """
    db = load_db()
    return set(db.keys())


def get_pending_leads() -> list[dict]:
    """Return all leads in 'pending' status (never successfully emailed)."""
    db = load_db()
    return [record for record in db.values() if record.get("outreach_status") == "pending"]


def upsert_leads(leads: list[dict]) -> dict:
    """
    Merge this run's leads into the persistent DB.
    - New leads  → added with outreach_status = 'pending'
    - Seen leads → run_count incremented, status updated if email was sent
    Returns the updated DB.
    """
    db = load_db()
    today = str(date.today())

    for lead in leads:
        domain = _domain_from_lead(lead)
        if not domain:
            continue

        send_status = lead.get("send_status", "")
        outreach_status = _send_status_to_outreach(send_status)

        if domain not in db:
            # Brand new lead
            db[domain] = {
                "name":             lead.get("name", ""),
                "email":            lead.get("email", ""),
                "phone":            lead.get("phone", ""),
                "website":          lead.get("website", ""),
                "address":          lead.get("address", ""),
                "industry":         lead.get("industry", ""),
                "first_seen":       today,
                "last_contacted":   today if outreach_status == "sent" else None,
                "outreach_status":  "guessed" if lead.get("email_details", {}).get("source") == "Pattern Guessing" else outreach_status,
                "email_source":     lead.get("email_details", {}).get("source", ""),
                "email_subject":    lead.get("email_subject", ""),
                "follow_up_1_sent": None,
                "follow_up_2_sent": None,
                "follow_up_3_sent": None,
                "closing_sent":     None,
                "notes":            "",
                "run_count":        1,
            }
        else:
            # Existing lead — update fields that may have improved
            existing = db[domain]
            existing["run_count"] = existing.get("run_count", 1) + 1

            # Fill in missing fields
            if not existing.get("email") and lead.get("email"):
                existing["email"] = lead["email"]
            if not existing.get("phone") and lead.get("phone"):
                existing["phone"] = lead["phone"]
            if not existing.get("industry") and lead.get("industry"):
                existing["industry"] = lead["industry"]
            # Backfill new fields on old records
            for field in ("follow_up_1_sent", "follow_up_2_sent", "follow_up_3_sent", "closing_sent"):
                existing.setdefault(field, None)
            existing.setdefault("notes", "")
            if not existing.get("email_source") and lead.get("email_details", {}).get("source"):
                existing["email_source"] = lead["email_details"]["source"]
            
            # If current lead was guessed, set status accordingly if not already contacted
            if lead.get("email_details", {}).get("source") == "Pattern Guessing":
                outreach_status = "guessed"

            # Only upgrade status along the lifecycle, never downgrade
            status_rank = {
                "pending": 0, "sent": 1,
                "follow_up_1": 2, "follow_up_2": 3, "follow_up_3": 4,
                "closing": 5, "replied": 6, "booked": 7,
                "closed": 8, "dead": 9, "skipped": 10,
                "guessed": 11,
            }
            current_rank = status_rank.get(existing.get("outreach_status", "pending"), 0)
            new_rank = status_rank.get(outreach_status, 0)
            if new_rank > current_rank:
                existing["outreach_status"] = outreach_status
                if outreach_status == "sent":
                    existing["last_contacted"] = today

    save_db(db)
    print(f"[Tracker] 💾 Lead DB updated — {len(db)} total leads on record.")
    return db


def update_status(domain: str, status: str) -> bool:
    """
    Manually update the outreach status for a lead.
    Returns True if the domain was found and updated.
    """
    valid_statuses = {
        "pending", "sent",
        "follow_up_1", "follow_up_2", "follow_up_3",
        "closing", "replied", "booked", "closed", "dead", "skipped",
    }
    if status not in valid_statuses:
        print(f"[Tracker] ❌ Invalid status '{status}'. Use: {valid_statuses}")
        return False

    db = load_db()
    # Try exact match first, then partial match
    key = domain.lower().strip()
    if key not in db:
        matches = [k for k in db if key in k]
        if len(matches) == 1:
            key = matches[0]
        elif len(matches) > 1:
            print(f"[Tracker] ⚠️ Ambiguous domain '{domain}' — matches: {matches}")
            return False
        else:
            print(f"[Tracker] ❌ Domain '{domain}' not found in DB.")
            return False

    old_status = db[key].get("outreach_status", "?")
    db[key]["outreach_status"] = status
    if status == "sent":
        db[key]["last_contacted"] = str(date.today())
    save_db(db)
    print(f"[Tracker] ✅ {key}: {old_status} → {status}")
    return True


def get_leads_due_for_followup() -> list:
    """
    Return leads that are due for their next follow-up step based on
    elapsed days since the previous step was sent.

    Timing gaps (configurable via .env):
      FOLLOWUP_1_DELAY_DAYS  — days after initial email before Step 1  (default: 3)
      FOLLOWUP_2_DELAY_DAYS  — days after Step 1 before Step 2          (default: 4)
      FOLLOWUP_3_DELAY_DAYS  — days after Step 2 before Step 3          (default: 7)
      CLOSING_DELAY_DAYS     — days after Step 3 before Closing         (default: 7)

    Using relative gaps produces absolute offsets: 3 / 7 / 14 / 21 days
    from the initial send — exactly as configured.

    Returns:
        list of (domain: str, record: dict, step: int)
    """
    import os as _os
    from datetime import date as _date

    delay_1 = int(_os.getenv("FOLLOWUP_1_DELAY_DAYS", 3))
    delay_2 = int(_os.getenv("FOLLOWUP_2_DELAY_DAYS", 4))
    delay_3 = int(_os.getenv("FOLLOWUP_3_DELAY_DAYS", 7))
    delay_4 = int(_os.getenv("CLOSING_DELAY_DAYS",    7))

    db    = load_db()
    today = _date.today()
    due   = []

    for domain, record in db.items():
        status = record.get("outreach_status", "pending")

        if status == "sent":
            ref = record.get("last_contacted")
            if ref and (_date.today() - _date.fromisoformat(ref)).days >= delay_1:
                due.append((domain, record, 1))

        elif status == "follow_up_1":
            ref = record.get("follow_up_1_sent")
            if ref and (today - _date.fromisoformat(ref)).days >= delay_2:
                due.append((domain, record, 2))

        elif status == "follow_up_2":
            ref = record.get("follow_up_2_sent")
            if ref and (today - _date.fromisoformat(ref)).days >= delay_3:
                due.append((domain, record, 3))

        elif status == "follow_up_3":
            ref = record.get("follow_up_3_sent")
            if ref and (today - _date.fromisoformat(ref)).days >= delay_4:
                due.append((domain, record, 4))

    return due


def mark_followup_sent(domain: str, step: int, dry_run: bool = False) -> bool:
    """
    Record that a follow-up step was sent for a domain.
    Updates the step-specific date field, advances outreach_status,
    and refreshes last_contacted.

    Args:
        domain:  bare domain string (e.g. 'acme.com')
        step:    1, 2, 3, or 4
        dry_run: if True, print what would happen but don't write to disk

    Returns:
        True on success, False if domain not found or invalid step.
    """
    _step_map = {
        1: ("follow_up_1_sent", "follow_up_1"),
        2: ("follow_up_2_sent", "follow_up_2"),
        3: ("follow_up_3_sent", "follow_up_3"),
        4: ("closing_sent",     "closing"),
    }
    if step not in _step_map:
        print(f"[Tracker] ❌ Invalid follow-up step {step}. Must be 1–4.")
        return False

    db  = load_db()
    key = domain.lower().strip()
    if key not in db:
        matches = [k for k in db if key in k]
        if len(matches) == 1:
            key = matches[0]
        else:
            print(f"[Tracker] ❌ Domain '{domain}' not found in DB.")
            return False

    date_field, new_status = _step_map[step]
    today = str(date.today())

    if dry_run:
        print(f"[Tracker] [DRY RUN] Would mark {key} → {new_status} (step {step})")
        return True

    record = db[key]
    record[date_field]       = today
    record["outreach_status"] = new_status
    record["last_contacted"]  = today
    save_db(db)
    print(f"[Tracker] ✅ {key}: step {step} sent → {new_status}")
    return True


# ── Reporting ─────────────────────────────────────────────────────────────────

def get_summary(db: dict = None) -> None:
    """Print a full lifecycle summary of all leads in the database."""
    if db is None:
        db = load_db()

    total = len(db)
    if total == 0:
        print("[Tracker] No leads in database yet.")
        return

    by_status: dict[str, int] = {}
    for record in db.values():
        s = record.get("outreach_status", "pending")
        by_status[s] = by_status.get(s, 0) + 1

    W = 42
    print("\n" + "=" * W)
    print("    LEAD HUNTER — ALL-TIME TRACKER")
    print("=" * W)
    print(f"  Total leads on record : {total}")
    print(f"  Pending (not emailed) : {by_status.get('pending', 0)}")
    print()
    print("  ── Outreach Sequence ─────────────────")
    print(f"  Sent (initial)        : {by_status.get('sent', 0)}")
    print(f"  Follow-up 1 sent      : {by_status.get('follow_up_1', 0)}")
    print(f"  Follow-up 2 sent      : {by_status.get('follow_up_2', 0)}")
    print(f"  Follow-up 3 sent      : {by_status.get('follow_up_3', 0)}")
    print(f"  Closing sent          : {by_status.get('closing', 0)}")
    print()
    print("  ── Outcomes ──────────────────────────")
    print(f"  Replied               : {by_status.get('replied', 0)}")
    print(f"  Call booked           : {by_status.get('booked', 0)}")
    print(f"  Closed                : {by_status.get('closed', 0)}")
    print(f"  Dead (no response)    : {by_status.get('dead', 0)}")
    print(f"  Skipped               : {by_status.get('skipped', 0)}")
    print(f"  Guessed (not sent)    : {by_status.get('guessed', 0)}")

    # Show leads currently in-sequence that are awaiting response
    in_sequence = [
        (domain, r) for domain, r in db.items()
        if r.get("outreach_status") in (
            "sent", "follow_up_1", "follow_up_2", "follow_up_3", "closing"
        )
    ]
    if in_sequence:
        print(f"\n  📬 In sequence ({len(in_sequence)} leads):")
        for domain, r in in_sequence:
            status = r.get("outreach_status", "?")
            print(f"    • {r.get('name', domain):<30} [{status}] — last: {r.get('last_contacted', 'never')}")

    wins = [(d, r) for d, r in db.items() if r.get("outreach_status") == "booked"]
    if wins:
        print(f"\n  🎯 Calls Booked ({len(wins)}):")
        for domain, r in wins:
            print(f"    • {r.get('name', domain)} <{r.get('email', '')}>")

    print("=" * W + "\n")


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile, shutil

    # Use a temp dir so we don't touch the real DB
    tmp_dir = tempfile.mkdtemp()
    original_db_file = DB_FILE

    # Monkey-patch DB_FILE for the test
    import lead_tracker as _self
    _self.DB_FILE = os.path.join(tmp_dir, "test_lead_db.json")

    test_leads = [
        {"name": "Acme Corp",    "website": "https://acme.com",    "email": "hello@acme.com",    "send_status": "sent"},
        {"name": "Beta Agency",  "website": "https://beta.co",     "email": "info@beta.co",      "send_status": "dry_run"},
        {"name": "Gamma Studio", "website": "https://gamma.io",    "email": "contact@gamma.io",  "send_status": "skipped"},
    ]

    print("--- Tracker Self-Test ---\n")
    print("[1] Upserting 3 leads...")
    _self.upsert_leads(test_leads)

    print("\n[2] Upserting same leads again (should not duplicate)...")
    _self.upsert_leads(test_leads)

    db = _self.load_db()
    assert len(db) == 3, f"Expected 3 unique leads, got {len(db)}"
    print(f"    ✅ Deduplication OK — {len(db)} unique leads")

    print("\n[3] Updating status for acme.com → follow_up...")
    _self.update_status("acme.com", "follow_up")

    print("\n[4] Summary:")
    _self.get_summary()

    shutil.rmtree(tmp_dir)
    print("Self-test passed ✅")
