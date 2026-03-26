import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define your service offer here — this is what GPT will pitch on your behalf
YOUR_SERVICE = os.getenv(
    "YOUR_SERVICE",
    (
        "I build lightweight AI automations for service businesses that automatically "
        "generate and follow up with leads — no new tools to learn, no monthly SaaS fee. "
        "Typically gets 5-10 new qualified leads per month for a business your size."
    ),
)


def generate_email(business: dict, your_service: str, research: dict = {}) -> dict:
    """
    Generate a SMYKM-style cold email for a business.
    Returns {"subject": "...", "body": "..."} or empty dict on failure.

    SMYKM = Show Me You Know Me — every email must prove
    it was written for THIS business, not a generic blast.
    """
    prompt = f"""
You are an expert cold email copywriter specializing in B2B outreach for service businesses.

Your task is to generate a highly personalized, short, and conversational cold email using the "Show Me You Know Me" (SMYKM) framework.

### Context

BUSINESS DETAILS:
- Company name: {business['name']}
- Location: {business.get('address', 'unknown')}
- Website: {business.get('website', 'unknown')}
- Industry rating/size signal: {business.get('rating', 'unknown')}

RESEARCH (if available):
{research if research else "None provided. Use business name and location to infer context."}

YOUR SERVICE:
{your_service}

### Goal

Write a cold email that:
* Feels human and not like a sales pitch
* Is under 100 words
* Uses simple, conversational language
* Creates curiosity instead of explaining everything
* Focuses on ONE clear idea

---

### Structure

1. Subject line:
   - Short (3–6 words)
   - Personalized with company name or idea

2. Opening:
   - Mention the company + a specific positive observation

3. Insight:
   - Highlight a likely pain point (e.g., scaling, lead follow-up, missed opportunities)

4. Offer:
   - Briefly mention AI automation solution (no jargon, no hard selling)

5. CTA:
   - Low friction, curiosity-based
   - Example: "Want me to share what I noticed?"

---

### Rules

* DO NOT use phrases like:
  - "We haven't met"
  - "I hope you're doing well"
  - "I wanted to reach out"
* DO NOT sound salesy or corporate
* DO NOT exceed 100 words
* DO NOT list features or benefits
* Keep tone casual and direct
* Sign off as: Pranay

Return ONLY this JSON, no markdown, no extra text:
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


def generate_emails_for_leads(leads: list[dict]) -> list[dict]:
    """
    Add 'email_subject' and 'email_body' fields to each lead that has an email address.
    Skips leads with no found email.
    """
    for lead in leads:
        if lead.get("email"):
            print(f"[AI] Generating SMYKM email for: {lead['name']}")
            result = generate_email(lead, YOUR_SERVICE)
            lead["email_subject"] = result.get("subject", "")
            lead["email_body"] = result.get("body", "")
            if lead["email_subject"]:
                print(f"[AI] Subject: {lead['email_subject']}")
        else:
            lead["email_subject"] = ""
            lead["email_body"] = ""
    return leads
