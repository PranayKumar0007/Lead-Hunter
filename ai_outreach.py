import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Removed global YOUR_SERVICE string to favor dynamic service personalization engine input


def generate_email(business: dict, your_service: str, research: dict = {}) -> dict:
    """
    Generate a SMYKM-style cold email for a business.
    Returns {"subject": "...", "body": "..."} or empty dict on failure.

    SMYKM = Show Me You Know Me — every email must prove
    it was written for THIS business, not a generic blast.
    """
    prompt = f"""
You are a cold email copywriter writing on behalf of a lead generation and appointment setting agency.

Your task: write a short, direct, results-focused cold email for the business below.

The tone should be casual yet confident — like a message from someone who has already figured something out and is sharing it, not pitching.

### BUSINESS DETAILS:
- Company name: {business['name']}
- Location: {business.get('address', 'unknown')}
- Website: {business.get('website', 'unknown')}

### RESEARCH (if available):
{research if research else "None. Infer from name and location."}

### SERVICE:
{your_service}

### SAMPLE EMAIL (use this as structural inspiration only — do NOT copy it):
Subject: quick thought on your lead flow + ads

Saw you're helping [students/niche] grow — quick thought.

Most [coaching institutes / edtech brands] I've seen struggle with consistent outbound alongside their ads.

We've been testing a system that finds high-intent prospects and writes outreach specific to them — so it doesn't feel like spam.

Might be worth trying alongside your current setup.

Happy to share a few leads if you're open.

### RULES:
- Under 100 words for the body
- No "I hope this finds you well", "We haven't met", or "I wanted to reach out"
- Reference the company by name at least once
- One clear idea, one soft CTA
- Sign off as: Pranay
- Subject: 4–7 words, specific and intriguing

Return ONLY this JSON (no markdown, no extra text):
{{
  "subject": "...",
  "body": "..."
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.85,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        # Validate expected keys are present
        if "subject" in result and "body" in result:
            return result
        print(f"[AI] Unexpected JSON shape for '{business['name']}': {result}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[AI] JSON parse error for '{business['name']}': {e}")
        return {}
    except Exception as e:
        print(f"[AI] Error generating email for '{business['name']}': {e}")
        return {}


def generate_emails_for_leads(leads: list[dict], your_service: str = "I build AI automations that automatically capture leads and handle follow-ups.") -> list[dict]:
    """
    Add 'email_subject' and 'email_body' fields to each lead that has an email address.
    Skips leads with no found email.
    """
    for lead in leads:
        if lead.get("email"):
            print(f"[AI] Generating SMYKM email for: {lead['name']}")
            result = generate_email(lead, your_service)
            lead["email_subject"] = result.get("subject", "")
            lead["email_body"] = result.get("body", "")
            if lead["email_subject"]:
                print(f"[AI] Subject: {lead['email_subject']}")
        else:
            lead["email_subject"] = ""
            lead["email_body"] = ""
    return leads
