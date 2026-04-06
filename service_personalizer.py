"""
service_personalizer.py - Generates dynamic pitch based on research data.
"""

def get_service_pitch(research_data: dict) -> str:
    """Return a personalized service pitch based on company industry."""
    if not research_data:
        research_data = {}
        
    industry = str(research_data.get("industry", "")).lower()
    name = str(research_data.get("name", "")).lower()
    combined = industry + " " + name

    if any(kw in combined for kw in ["coach", "tutor", "edtech", "education", "institute", "academy", "learning", "course", "upskill"]):
        return "I help coaching institutes and edtech companies book more student calls by finding high-intent prospects and reaching out to them with outreach that actually converts — no ads needed."
    elif "plumb" in combined:
        return "I help plumbing businesses capture urgent leads and automate bookings so no opportunity is missed."
    elif "dent" in combined:
        return "I help dental clinics reduce no-shows and automate appointment reminders."
    elif "real estate" in combined:
        return "I help real estate teams capture and qualify leads automatically."
    else:
        return "I help businesses book more qualified calls by automating their outbound prospecting and follow-up."

