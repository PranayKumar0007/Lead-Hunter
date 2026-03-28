"""
service_personalizer.py - Generates dynamic pitch based on research data.
"""

def get_service_pitch(research_data: dict) -> str:
    """Return a personalized service pitch based on company industry."""
    if not research_data:
        research_data = {}
        
    industry = str(research_data.get("industry", "")).lower()
    
    if "plumb" in industry:
        return "I help plumbing businesses capture urgent leads and automate bookings so no opportunity is missed."
    elif "dent" in industry:
        return "I help dental clinics reduce no-shows and automate appointment reminders."
    elif "real estate" in industry:
        return "I help real estate teams capture and qualify leads automatically."
    else:
        return "I help local businesses automate lead handling and customer follow-ups to increase conversions."
