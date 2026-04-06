"""
follow_up_writer.py — AI-powered follow-up email sequence generator
====================================================================
Generates 4 follow-up emails for leads that haven't responded to the
initial cold email.

  Step 1 (Day  3) — Gentle bump:  "Did this land?"
  Step 2 (Day  7) — Value-add:    Industry insight + concrete result
  Step 3 (Day 14) — Last try:     Direct, brief, honest final attempt
  Step 4 (Day 21) — Closing:      Book a call with calendar link embedded

Each email uses "Re: {original_subject}" to maintain inbox thread context
and boost open rates on follow-ups.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CALENDAR_LINK = os.getenv("CALENDAR_LINK", "https://calendly.com/yourname/15min")

# ── Step prompts ──────────────────────────────────────────────────────────────

_STEP_SYSTEM_PROMPTS = {
    1: """\
You are writing a follow-up cold email on behalf of Pranay, a lead generation \
automation expert.

This is a Day 3 "did this land?" bump. The recipient has not replied to the \
initial cold email.

Rules:
- 2–3 sentences MAX for the body
- Do NOT apologize for following up
- Do NOT repeat or re-pitch the original message
- Sound human — like a real person double-checking, not a bot
- Ask ONE low-commitment question (e.g. "Is this on your radar at all?")
- Sign off as: Pranay
- Subject MUST be exactly: Re: {original_subject}

Return ONLY valid JSON, no markdown:
{{"subject": "Re: {original_subject}", "body": "..."}}""",

    2: """\
You are writing a follow-up cold email on behalf of Pranay, a lead generation \
automation expert.

This is the Day 7 follow-up. The lead still hasn't responded. Your goal is \
to add NEW value — not repeat the pitch.

Your job:
- Open with one sharp, industry-specific insight that feels surprising and true
  (e.g. "Most [industry] businesses lose 30–40% of inbound leads from slow follow-up alone")
- Connect it naturally to what Pranay's automation system solves
- Include one real-sounding outcome or result
- End with a soft, no-pressure CTA

Rules:
- Under 90 words for the body
- No filler openers ("Hope you're well", "Just wanted to follow up")
- Sign off as: Pranay
- Subject MUST be exactly: Re: {original_subject}

Return ONLY valid JSON, no markdown:
{{"subject": "Re: {original_subject}", "body": "..."}}""",

    3: """\
You are writing a "last genuine attempt" cold email on behalf of Pranay, a \
lead generation automation expert.

This is the Day 14 email. Be honest — make it clear this is your last reach-out.

Rules:
- Open with something like "Last one from me —" or "I'll keep this short —"
- Mention you won't follow up again after this (non-pushy way)
- Offer one specific, tangible outcome if they respond now
  (e.g. "I can map out exactly how this would work for [Company] in 15 min")
- Under 65 words for the body
- NOT guilt-trippy or needy — just clear and human
- Sign off as: Pranay
- Subject MUST be exactly: Re: {original_subject}

Return ONLY valid JSON, no markdown:
{{"subject": "Re: {original_subject}", "body": "..."}}""",

    4: """\
You are writing the final "closing" cold email on behalf of Pranay, a lead \
generation automation expert.

This is the Day 21 email. Make saying yes dead simple with a direct calendar link.

Rules:
- Open with something like "I'll make this easy —" or "One last thing —"
- The entire ask: a 15-minute call, no prep needed from them
- Embed the calendar link naturally in the body (not just pasted at the end)
- Confident, NOT desperate
- Under 55 words for the body
- Sign off as: Pranay
- Subject MUST be exactly: Re: {original_subject}

Calendar link to embed: {calendar_link}

Return ONLY valid JSON, no markdown:
{{"subject": "Re: {original_subject}", "body": "..."}}""",
}

STEP_LABELS = {
    1: "Day 3 — Gentle Bump",
    2: "Day 7 — Value Add",
    3: "Day 14 — Last Try",
    4: "Day 21 — Closing Call Invite",
}


# ── Core generator ────────────────────────────────────────────────────────────

def generate_followup_email(lead: dict, step: int) -> dict:
    """
    Generate a follow-up email for a lead at the given sequence step (1–4).

    Args:
        lead: dict with at minimum: name, email, email_subject (original subject)
              Optional enrichers: website, address, industry
        step: 1 (Day 3), 2 (Day 7), 3 (Day 14), 4 (Day 21 closing)

    Returns:
        {"subject": "Re: ...", "body": "..."} or {} on failure
    """
    if step not in _STEP_SYSTEM_PROMPTS:
        print(f"[FollowUp] ❌ Invalid step {step}. Must be 1–4.")
        return {}

    original_subject = lead.get("email_subject", "our last note") or "our last note"

    system_prompt = _STEP_SYSTEM_PROMPTS[step].format(
        original_subject=original_subject,
        calendar_link=CALENDAR_LINK,
    )

    # Business context sent as the user message
    context_lines = [
        f"Company name: {lead.get('name', 'this company')}",
        f"Industry: {lead.get('industry', 'not specified')}",
        f"Location: {lead.get('address', 'not specified')}",
        f"Website: {lead.get('website', 'not specified')}",
        f"Original email subject: {original_subject}",
    ]
    user_content = "\n".join(context_lines)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=350,
            temperature=0.82,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        if "subject" in result and "body" in result:
            return result
        print(f"[FollowUp] ⚠️  Unexpected JSON shape for '{lead.get('name')}': {result}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[FollowUp] JSON parse error for '{lead.get('name')}': {e}")
        return {}
    except Exception as e:
        print(f"[FollowUp] Error generating step {step} for '{lead.get('name')}': {e}")
        return {}


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mock_lead = {
        "name": "Acme Digital Agency",
        "email": "hello@acme.com",
        "address": "Hyderabad, India",
        "website": "https://acme.com",
        "email_subject": "quick thought on your lead flow",
        "industry": "digital marketing agency",
    }

    print("--- Follow-Up Writer Self-Test ---\n")
    for step in range(1, 5):
        print(f"\n{'=' * 52}")
        print(f"  Step {step}: {STEP_LABELS[step]}")
        print("=" * 52)
        result = generate_followup_email(mock_lead, step)
        if result:
            print(f"  Subject : {result['subject']}")
            print(f"  Body    :\n{result['body']}")
        else:
            print("  ❌ Failed to generate email.")
