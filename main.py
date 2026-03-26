"""
Lead Hunter — main pipeline orchestrator
=========================================
Pipeline:
  1. maps_fetcher       → find service businesses via Google Maps
  2. email_finder       → find their email via Hunter.io
  3. company_researcher → scrape & summarize each business website
  4. ai_outreach        → generate personalized SMYKM cold email via GPT-4o-mini
  5. email_sender       → send (or dry-run) via Gmail SMTP
  6. report             → save CSV + print summary

IMPORTANT:
  ACTUALLY_SEND = False  → dry run (safe, default)
  ACTUALLY_SEND = True   → live send (only flip after reviewing CSV!)
"""

from maps_fetcher import get_leads
from email_finder import enrich_leads_with_emails
from company_researcher import research_company
from ai_outreach import generate_emails_for_leads, generate_email, YOUR_SERVICE
from email_sender import send_emails_for_leads
from report import save_to_csv, print_summary

# ─── SAFETY SWITCH ────────────────────────────────────────────────────────────
#  Set to True ONLY after you've reviewed the dry-run CSV in output/leads.csv
ACTUALLY_SEND = False
# ──────────────────────────────────────────────────────────────────────────────


def main():
    print("\n🚀 Starting Lead Hunter pipeline...\n")

    # Step 1: Find businesses
    leads = get_leads()
    if not leads:
        print("No leads found. Check your Google Maps API key or search config.")
        return

    # Step 2: Find emails
    leads = enrich_leads_with_emails(leads)

    # Step 3: Research each business website + generate SMYKM cold email
    for lead in leads:
        if lead.get("email"):
            print(f"[Research] Researching: {lead['name']}...")
            research = research_company(lead)
            lead["email_subject"], lead["email_body"] = "", ""
            result = generate_email(lead, YOUR_SERVICE, research)
            lead["email_subject"] = result.get("subject", "")
            lead["email_body"] = result.get("body", "")
            if lead["email_subject"]:
                print(f"[AI] Subject: {lead['email_subject']}")
        else:
            lead["email_subject"] = ""
            lead["email_body"] = ""

    # Step 4: Send (or dry run)
    if not ACTUALLY_SEND:
        print("\n⚠️  DRY RUN MODE — no emails will be sent.")
        print("   Review output/leads.csv, then set ACTUALLY_SEND = True to go live.\n")
    leads = send_emails_for_leads(leads, actually_send=ACTUALLY_SEND)

    # Step 5: Save CSV report + print summary
    save_to_csv(leads)
    print_summary(leads)


if __name__ == "__main__":
    main()
