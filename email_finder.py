import os
import requests
import time
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

SNOV_CLIENT_ID = os.getenv("SNOV_CLIENT_ID")
SNOV_CLIENT_SECRET = os.getenv("SNOV_CLIENT_SECRET")
SNOV_AUTH_URL = "https://api.snov.io/v1/oauth/access_token"
SNOV_DOMAIN_SEARCH_URL = "https://api.snov.io/v2/domain-emails-with-info"

_snov_token_cache = {
    "token": None,
    "expires_at": 0
}

def extract_domain(website: str) -> str:
    """Extract bare domain from a full URL."""
    if not website:
        return ""
    parsed = urlparse(website if website.startswith("http") else f"https://{website}")
    return parsed.netloc.replace("www.", "")

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

def find_emails(domain: str) -> list[str]:
    """
    Use Snov.io domain search to find the most likely emails at a domain.
    Filters out support/noreply logic, prioritizes founders/owner/info.
    Returns the top 1-2 emails.
    """
    if not domain:
        return []
        
    token = get_snov_token()
    if not token:
        return []

    params = {
        "domain": domain,
        "type": "all",
        "limit": 50, # Get a healthy sample to filter
    }
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        resp = requests.get(SNOV_DOMAIN_SEARCH_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("success"):
            print(f"[Snov.io] API returned unsuccessful for {domain}.")
            return []
            
        emails_data = data.get("emails", [])
        if not emails_data:
            return []
            
        filtered_emails = []
        for e in emails_data:
            email_str = e.get("email", "").lower()
            status = e.get("status", "")
            
            # Smart filtering rules - Avoid generic non-sales addresses
            if email_str.startswith("noreply@") or email_str.startswith("support@") or email_str.startswith("admin@"):
                continue
                
            # Keep valid and catch-all emails (avoid invalid)
            if status == "invalid":
                continue
                
            filtered_emails.append(e)
            
        # Score the emails to surface the best ones
        def score_email(e):
            score = 0
            email_val = e.get("email", "").lower()
            status = e.get("status", "")
            
            # Valid emails are preferred over catch-all or unverified
            if status == "valid":
                score += 10
                
            # Prioritize target roles if available in firstName/lastName
            position = str(e.get("position", "")).lower()
            
            if "founder" in position or "owner" in position or "ceo" in position:
                score += 20
                
            # If no position, but prefixes match high-value generic roles
            if email_val.startswith("info@") or email_val.startswith("hello@") or email_val.startswith("contact@"):
                score += 5
                
            return score
            
        # Sort emails by score descending
        filtered_emails.sort(key=score_email, reverse=True)
        
        # Extract at most 2 top email strings
        best_emails = [e["email"] for e in filtered_emails[:2]]
        return best_emails

    except Exception as e:
        print(f"[Snov.io] Domain search error for {domain}: {e}")
        return []

def find_email_for_lead(lead: dict) -> str:
    """
    Given a lead dict with 'website' key, find their email.
    Grabs the top email from find_emails. Falls back to empty string.
    """
    domain = extract_domain(lead.get("website", ""))
    if not domain:
        print(f"[Snov.io] No website for '{lead.get('name')}' — skipping email lookup.")
        return ""

    print(f"[Snov.io] Looking up email for domain: {domain}")
    emails = find_emails(domain)
    if emails:
        top_email = emails[0]
        print(f"[Snov.io] Found: {top_email} (from {len(emails)} top options)")
        return top_email
    else:
        print(f"[Snov.io] No distinct email found for {domain}.")
        return ""

def enrich_leads_with_emails(leads: list[dict]) -> list[dict]:
    """Add 'email' field to each lead dict."""
    for lead in leads:
        lead["email"] = find_email_for_lead(lead)
    return leads
