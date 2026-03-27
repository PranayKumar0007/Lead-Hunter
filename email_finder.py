import os
import re
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

# Out of credits handling is incorporated directly within try_snov_io

# === MODIFIED: WATERFALL STRATEGY ===
def try_snov_io(domain: str):
    """
    Try to find email using Snov.io.
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

# === NEW: WEBSITE SCRAPER FALLBACK ===
def scrape_email_from_website(company_website: str, domain: str):
    """
    Scrape emails directly from the company's own website.
    Checks the homepage, /contact, and /about pages.
    Returns a standard dict or None.
    """
    if not company_website:
        return None

    # Normalize base URL
    base_url = company_website.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    # Pages to check in order
    pages_to_check = [
        base_url,
        f"{base_url}/contact",
        f"{base_url}/contact-us",
        f"{base_url}/about",
        f"{base_url}/about-us",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Regex to find email addresses
    email_regex = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

    # Junk prefixes to skip
    junk_prefixes = ("noreply", "no-reply", "support", "admin", "unsubscribe", "bounce", "mailer")
    # Junk domains (image hosts, etc.)
    junk_domains = ("sentry.io", "wixpress.com", "example.com", "schema.org", "googleapis.com")

    found_emails = []

    for page_url in pages_to_check:
        try:
            resp = requests.get(page_url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                continue

            raw_emails = email_regex.findall(resp.text)

            for email in raw_emails:
                email_lower = email.lower()
                # Skip junk
                if email_lower.startswith(junk_prefixes):
                    continue
                if any(jd in email_lower for jd in junk_domains):
                    continue
                # Only keep emails that match the company domain
                if domain and domain not in email_lower:
                    continue
                if email_lower not in found_emails:
                    found_emails.append(email_lower)

            if found_emails:
                break  # Stop after finding emails on first successful page

        except Exception:
            continue  # Silently skip pages that fail to load

    if not found_emails:
        return None

    # Score emails — prefer personal/contact addresses over generic ones
    def score_scraped(email):
        score = 0
        local = email.split("@")[0].lower()
        if local in ("info", "hello", "contact", "enquiry", "enquiries", "query"):
            score += 5
        # Personal-looking emails (firstname.lastname) get a boost
        if "." in local and len(local) > 5:
            score += 8
        return score

    found_emails.sort(key=score_scraped, reverse=True)
    best_email = found_emails[0]

    local_part = best_email.split("@")[0].lower()
    if local_part in ("info", "hello", "contact", "enquiry"):
        confidence = "medium"  # Real email from their site, but generic
    else:
        confidence = "high"    # Looks like a personal/direct email

    print(f"✅ Found via website scrape: {best_email}")
    return {
        "email": best_email,
        "source": "Website Scrape",
        "confidence": confidence,
        "name": "",
        "title": ""
    }

def guess_email_pattern(domain: str):
    if not domain:
        return None
    guessed = f"info@{domain}"
    print(f"⚠️ Guessed pattern: {guessed}")
    return {
        "email": guessed,
        "source": "Pattern Guessing",
        "confidence": "low",
        "name": "",
        "title": ""
    }

# === MODIFIED: WATERFALL STRATEGY ===
def find_email(company_name, domain, company_website=None):
    if not domain and company_website:
        domain = extract_domain(company_website)

    if not domain:
        print(f"❌ No email found for {company_name}")
        return None

    # Step 1: Try Snov.io
    result = try_snov_io(domain)
    if result == "OUT_OF_CREDITS":
        print("⚠️ Snov.io exhausted, trying website scrape...")
    elif result:
        return result

    # Step 2: Scrape the company's own website
    if company_website:
        print(f"[Scraper] Snov.io found nothing, scraping {company_website}...")
        result = scrape_email_from_website(company_website, domain)
        if result:
            return result

    # Step 3: Last resort — pattern guessing
    result = guess_email_pattern(domain)
    if result:
        return result

    print(f"❌ No email found for {company_name}")
    return None

def find_email_for_lead(lead: dict) -> str:
    """Compatibility wrapper for old interface."""
    domain = extract_domain(lead.get("website", ""))
    company_name = lead.get("name", "Unknown Company")
    
    result = find_email(company_name, domain, lead.get("website", ""))
    if result:
        return result["email"]
    return ""

def enrich_leads_with_emails(leads: list[dict]) -> list[dict]:
    """Add 'email' and 'email_details' fields to each lead dict."""
    for lead in leads:
        company_name = lead.get("name", "Unknown Company")
        domain = extract_domain(lead.get("website", ""))
        
        result = find_email(company_name, domain, lead.get("website", ""))
        if result:
            lead["email"] = result["email"]
            lead["email_details"] = result
        else:
            lead["email"] = ""
            
    return leads

if __name__ == "__main__":
    # Test with real websites to validate scraping fallback
    test_leads = [
        ("Web Rocz", "webrocz.com", "https://www.webrocz.com"),
        ("Digital i360", "digitali360.com", "https://digitali360.com"),
        ("BrandingNuts", "brandingnuts.com", "https://brandingnuts.com"),
    ]

    print("--- Testing Email Finder Pipeline ---")
    for company_name, domain, website in test_leads:
        print(f"\n🔍 Testing: {company_name} ({domain})")
        res = find_email(company_name, domain, website)
        print(f"   → Result: {res}")
