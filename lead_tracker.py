"""
lead_tracker.py — Persistent lead database for Lead Hunter
============================================================
Stores all leads across runs in output/lead_db.json.
Keys leads by domain so duplicates are never counted twice.

Statuses:
  pending    — found, not yet emailed
  sent       — initial email sent
  follow_up  — needs a follow-up
  skipped    — no email / opted out
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
    """Return the set of domains already in the database."""
    db = load_db()
    return set(db.keys())


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
                "first_seen":       today,
                "last_contacted":   today if outreach_status == "sent" else None,
                "outreach_status":  outreach_status,
                "email_subject":    lead.get("email_subject", ""),
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

            # Only upgrade status (pending → sent → follow_up), never downgrade
            status_rank = {"pending": 0, "sent": 1, "follow_up": 2, "skipped": 3}
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
    valid_statuses = {"pending", "sent", "follow_up", "skipped"}
    if status not in valid_statuses:
        print(f"[Tracker] ❌ Invalid status '{status}'. Use: {valid_statuses}")
        return False

    db = load_db()
    # Try exact match first, then partial match
    key = domain.lower().strip()
    if key not in db:
        # Try to find by partial domain
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


# ── Reporting ─────────────────────────────────────────────────────────────────

def get_summary(db: dict = None) -> None:
    """Print a summary of all leads in the database."""
    if db is None:
        db = load_db()

    total = len(db)
    if total == 0:
        print("[Tracker] No leads in database yet.")
        return

    by_status = {}
    for record in db.values():
        s = record.get("outreach_status", "pending")
        by_status[s] = by_status.get(s, 0) + 1

    print("\n" + "=" * 42)
    print("    LEAD HUNTER — ALL-TIME TRACKER")
    print("=" * 42)
    print(f"  Total leads on record : {total}")
    print(f"  Pending (not emailed) : {by_status.get('pending', 0)}")
    print(f"  Sent                  : {by_status.get('sent', 0)}")
    print(f"  Need follow-up        : {by_status.get('follow_up', 0)}")
    print(f"  Skipped               : {by_status.get('skipped', 0)}")

    follow_ups = [
        (domain, r) for domain, r in db.items()
        if r.get("outreach_status") == "follow_up"
    ]
    if follow_ups:
        print("\n  📬 Follow-up required:")
        for domain, r in follow_ups:
            print(f"    • {r.get('name', domain)} <{r.get('email', '')}> — last contacted: {r.get('last_contacted', 'never')}")

    print("=" * 42 + "\n")


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
