"""
Lead Hunter — main pipeline orchestrator
=========================================
Pipeline:
  1. lead_tracker       → load known domains to skip already-contacted leads
  2. maps_fetcher       → find FRESH service businesses via Google Maps
  3. email_finder       → find their email (Snov.io → website scrape → pattern)
  4. company_researcher → scrape & summarize each business website
  5. ai_outreach        → generate personalized SMYKM cold email via GPT-4o-mini
  6. email_sender       → send (or dry-run) via Zoho SMTP
  7. lead_tracker       → save run results to persistent DB
  8. report             → save CSV + print summary

IMPORTANT:
  ACTUALLY_SEND = False  → dry run (safe, default)
  ACTUALLY_SEND = True   → live send (only flip after reviewing CSV!)

Optional flags:
  python main.py --run-followups   → run full pipeline AND follow-up pass
"""

import sys
from maps_fetcher import get_fresh_leads
from email_finder import enrich_leads_with_emails
from company_researcher import research_company
from ai_outreach import generate_emails_for_leads, generate_email
from email_sender import send_emails_for_leads
from report import save_to_csv, print_summary
from lead_tracker import get_known_domains, upsert_leads, get_summary
from service_personalizer import get_service_pitch
from snov_tracker import print_snov_status

# ─── SAFETY SWITCH ────────────────────────────────────────────────────────────
#  Set to True ONLY after you've reviewed the dry-run CSV in output/leads.csv
ACTUALLY_SEND = False
# ──────────────────────────────────────────────────────────────────────────────


def main():
    print("\n🚀 Starting Lead Hunter pipeline...\n")
    print_snov_status()

    # Step 1: Load known domains to skip already-contacted leads
    known_domains = get_known_domains()
    if known_domains:
        print(f"[Tracker] 📋 {len(known_domains)} leads already in DB — will skip them.\n")

    # Step 2: Find FRESH businesses (skips known domains, fetches more pages if needed)
    leads = get_fresh_leads(known_domains=known_domains)
    if not leads:
        print("No fresh leads found. All nearby businesses may already be in your DB.")
        print("Try expanding SEARCH_RADIUS_METERS or changing SEARCH_QUERY in .env")
        return

    # Step 3: Find emails
    leads = enrich_leads_with_emails(leads)

    # Step 4: Research each business website + generate SMYKM cold email
    for lead in leads:
        if lead.get("email"):
            print(f"[Research] Researching: {lead['name']}...")
            research = research_company(lead)
            service_pitch = get_service_pitch(research)
            lead["email_subject"], lead["email_body"] = "", ""
            result = generate_email(lead, service_pitch, research)
            lead["email_subject"] = result.get("subject", "")
            lead["email_body"] = result.get("body", "")
            if lead["email_subject"]:
                print(f"[AI] Subject: {lead['email_subject']}")
        else:
            lead["email_subject"] = ""
            lead["email_body"] = ""

    # Step 5: Send (or dry run)
    if not ACTUALLY_SEND:
        print("\n⚠️  DRY RUN MODE — no emails will be sent.")
        print("   Review output/leads.csv, then set ACTUALLY_SEND = True to go live.\n")
    leads = send_emails_for_leads(leads, actually_send=ACTUALLY_SEND)

    # Step 6: Save to persistent lead DB
    upsert_leads(leads)

    # Step 7: Save CSV report + print per-run summary
    save_to_csv(leads)
    print_summary(leads)

    # Step 8: Print all-time tracker summary
    get_summary()
    print_snov_status()


if __name__ == "__main__":
    main()
    # Optionally run the follow-up pass in the same invocation
    if "--run-followups" in sys.argv:
        from followup_runner import run_followup_pass
        print("\n" + "—" * 50)
        print("  Running follow-up pass...")
        print("—" * 50)
        run_followup_pass()

