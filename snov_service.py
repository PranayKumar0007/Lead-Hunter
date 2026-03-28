"""
snov_service.py - Isolated module for interacting with the Snov.io API.
Handles authentication, tracking, eligibility caching, and wrapper functions.
"""

import os
import requests
import time
from dotenv import load_dotenv
from snov_tracker import can_use_snov, increment_snov_usage

load_dotenv()

SNOV_CLIENT_ID = os.getenv("SNOV_CLIENT_ID")
SNOV_CLIENT_SECRET = os.getenv("SNOV_CLIENT_SECRET")
SNOV_AUTH_URL = "https://api.snov.io/v1/oauth/access_token"
SNOV_DOMAIN_SEARCH_URL = "https://api.snov.io/v2/domain-emails-with-info"

_snov_token_cache = {
    "token": None,
    "expires_at": 0
}

def get_snov_token():
    """Fetch an OAuth access token from Snov.io, using an in-memory cache to avoid repeated requests."""
    global _snov_token_cache
    now = time.time()
    
    # Use cached token if valid (buffer of 60 seconds)
    if _snov_token_cache["token"] and _snov_token_cache["expires_at"] > now + 60:
        return _snov_token_cache["token"]
        
    if not SNOV_CLIENT_ID or not SNOV_CLIENT_SECRET:
        print("[Snov.io] Credentials missing in environment variables.")
        return None
        
    try:
        resp = requests.post(SNOV_AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": SNOV_CLIENT_ID,
            "client_secret": SNOV_CLIENT_SECRET
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _snov_token_cache["token"] = data.get("access_token")
        # Default expiration is typically 3600 seconds, fallback to 3000 if not provided
        expires_in = int(data.get("expires_in", 3600))
        _snov_token_cache["expires_at"] = now + expires_in
        return _snov_token_cache["token"]
    except Exception as e:
        print(f"[Snov.io] Authentication failed: {e}")
        return None

def try_snov_io(domain: str):
    """
    Try to find email using Snov.io API.
    Returns standard dict, "OUT_OF_CREDITS", or None.
    """
    if not domain:
        return None
        
    token = get_snov_token()
    if not token:
        return None

    params = {
        "domain": domain,
        "type": "all",
        "limit": 50,
    }
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        resp = requests.get(SNOV_DOMAIN_SEARCH_URL, params=params, headers=headers, timeout=15)
        
        # Check for out of credits
        if resp.status_code in [402, 429]:
            print("⚠️ Snov.io out of credits")
            return "OUT_OF_CREDITS"
            
        if resp.status_code != 200:
            return None
            
        data = resp.json()
        
        # Check error message in json
        if "error" in data:
            error_msg = str(data["error"]).lower()
            if any(keyword in error_msg for keyword in ["credit", "limit", "quota"]):
                print("⚠️ Snov.io out of credits")
                return "OUT_OF_CREDITS"
                
        if not data.get("success"):
            return None
            
        emails_data = data.get("emails", [])
        if not emails_data:
            return None
            
        filtered_emails = []
        for e in emails_data:
            email_str = e.get("email", "").lower()
            status = e.get("status", "")
            
            if email_str.startswith("noreply@") or email_str.startswith("support@") or email_str.startswith("admin@"):
                continue
                
            if status == "invalid":
                continue
                
            filtered_emails.append(e)
            
        def score_email(e):
            score = 0
            email_val = e.get("email", "").lower()
            status = e.get("status", "")
            
            if status == "valid": 
                score += 10
                
            position = str(e.get("position", "")).lower()
            if any(r in position for r in ["founder", "owner", "ceo"]): 
                score += 20
                
            if email_val.startswith("info@") or email_val.startswith("hello@") or email_val.startswith("contact@"): 
                score += 5
                
            return score
            
        filtered_emails.sort(key=score_email, reverse=True)
        
        if filtered_emails:
            best = filtered_emails[0]
            email = best.get("email", "")
            first_name = best.get("firstName", "")
            last_name = best.get("lastName", "")
            name = (f"{first_name} {last_name}").strip()
            title = best.get("position", "")
            
            title_lower = title.lower()
            if any(r in title_lower for r in ["founder", "owner", "ceo"]):
                confidence = "high"
            elif email.startswith("info@") or email.startswith("hello@") or email.startswith("contact@"):
                confidence = "low"
            else:
                confidence = "medium"
                
            print(f"✅ Found via Snov.io: {email}")
            return {
                "email": email,
                "source": "Snov.io",
                "confidence": confidence,
                "name": name,
                "title": title
            }
            
    except Exception as e:
        print(f"Snov.io error: {e}")
        return None
        
    return None

GENERIC_PROVIDERS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"}
HIGH_VALUE_NICHES = [n.strip().lower() for n in os.getenv("HIGH_VALUE_NICHES", "plumber,dentist,real estate").split(",")]

def is_snov_eligible(lead: dict, domain: str) -> bool:
    """Returns True if the lead is eligible for a paid Snov lookup."""
    if not domain:
        return False
        
    if domain.lower() in GENERIC_PROVIDERS:
        print(f"⚠️ Snov skipped — generic provider: {domain}")
        return False
        
    if HIGH_VALUE_NICHES and HIGH_VALUE_NICHES[0]:
        name_lower = lead.get("name", "").lower()
        if not any(n in name_lower for n in HIGH_VALUE_NICHES):
            print(f"⚠️ Snov skipped — '{name_lower}' not in high-value niches {HIGH_VALUE_NICHES}")
            return False

    return True

def find_email_with_snov(lead: dict, domain: str):
    """Safe wrapper around Snov.io API with strict credit control."""
    if not can_use_snov():
        print("⚠️ Snov skipped — 0 credits remaining.")
        return None
        
    if not is_snov_eligible(lead, domain):
        return None
        
    print(f"[Snov.io] Attempting lookup for {domain}...")
    result = try_snov_io(domain)
    
    if result == "OUT_OF_CREDITS":
        print("⚠️ Snov.io exhausted via API response.")
        return None
        
    if result and "email" in result:
        increment_snov_usage()
        return result
        
    return None
