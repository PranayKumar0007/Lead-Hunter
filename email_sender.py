import os
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

ZOHO_EMAIL = os.getenv("ZOHO_EMAIL")
ZOHO_APP_PASSWORD = os.getenv("ZOHO_APP_PASSWORD")
SMTP_HOST = "smtp.zoho.in"
SMTP_PORT = 587

MAX_RETRIES = 3
MAX_EMAILS_PER_RUN = int(os.getenv("MAX_EMAILS_PER_RUN", 25))


def send_email(to_address: str, subject: str, body: str) -> bool:
    """
    Send a single email via Zoho SMTP with retry logic.
    Returns True on success, False on failure.
    """
    if not ZOHO_EMAIL or not ZOHO_APP_PASSWORD:
        print("[SMTP] ✗ Missing ZOHO_EMAIL or ZOHO_APP_PASSWORD in environment variables.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ZOHO_EMAIL
    msg["To"] = to_address
    msg.attach(MIMEText(body, "plain"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(ZOHO_EMAIL, ZOHO_APP_PASSWORD)
                server.sendmail(ZOHO_EMAIL, to_address, msg.as_string())
            print(f"[SMTP] ✓ Sent to {to_address}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            # Auth errors are usually fatal, don't retry
            print(f"[SMTP] ✗ Authentication failed for {ZOHO_EMAIL}: {e}")
            return False
        except smtplib.SMTPException as e:
            # Other SMTP errors might be transient
            print(f"[SMTP] ⚠ SMTP error on attempt {attempt}/{MAX_RETRIES} for {to_address}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
        except Exception as e:
            print(f"[SMTP] ✗ Unexpected error on attempt {attempt}/{MAX_RETRIES} for {to_address}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    print(f"[SMTP] ✗ Failed to send to {to_address} after {MAX_RETRIES} attempts.")
    return False


def send_emails_for_leads(leads: list[dict], actually_send: bool = False) -> list[dict]:
    """
    Send cold emails to all leads that have both an email and an email_body.

    actually_send=False  → dry run, marks status as 'dry_run'
    actually_send=True   → actually sends via Zoho SMTP
    """
    sent_count = 0
    for lead in leads:
        if not lead.get("email") or not lead.get("email_body"):
            lead["send_status"] = "skipped"
            continue

        if sent_count >= MAX_EMAILS_PER_RUN:
            print(f"[SMTP] Reached threshold of {MAX_EMAILS_PER_RUN} emails. Skipping remaining for this run.")
            continue

        subject = lead.get("email_subject") or f"Quick question for {lead['name']}"

        if not actually_send:
            print(f"[DRY RUN] Would send to {lead['email']} — {lead['name']}")
            lead["send_status"] = "dry_run"
            sent_count += 1
        else:
            success = send_email(lead["email"], subject, lead["email_body"])
            if success:
                lead["send_status"] = "sent"
                sent_count += 1
                
                # Introduce a random delay for safety
                delay = random.randint(5, 12)
                print(f"[SMTP] ⏳ Waiting {delay}s before next send to avoid spam detection...")
                time.sleep(delay)
            else:
                lead["send_status"] = "failed"

    return leads
