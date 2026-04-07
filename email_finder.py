import os
import re
import requests
import time
from dotenv import load_dotenv
from urllib.parse import urlparse
from snov_service import find_email_with_snov

load_dotenv()

def extract_domain(url: str) -> str:
    """Extract bare domain (e.g. 'example.com') from a URL or domain string."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    # Strip www.
    domain = re.sub(r"^www\.", "", domain).lower()
    return domain.split("/")[0]  # Remove any trailing path segments

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
def get_email(lead: dict, domain: str, company_website: str):
    company_name = lead.get("name", "Unknown Company")
    
    if not domain and company_website:
        domain = extract_domain(company_website)

    if not domain:
        print(f"❌ No email found for {company_name}")
        return None

    # Step 1: Try Scraping company's own website first (FREE)
    if company_website:
        result = scrape_email_from_website(company_website, domain)
        if result:
            return result

    # Step 2: Fallback to Snov.io (PAID) via SAFE wrapper
    result = find_email_with_snov(lead, domain)
    if result:
        return result

    # Step 3: Last resort — pattern guessing (FREE)
    result = guess_email_pattern(domain)
    if result:
        return result

    print(f"❌ No email found for {company_name}")
    return None

def find_email_for_lead(lead: dict) -> str:
    """Compatibility wrapper for old interface."""
    domain = extract_domain(lead.get("website", ""))
    
    result = get_email(lead, domain, lead.get("website", ""))
    if result:
        return result["email"]
    return ""

def enrich_leads_with_emails(leads: list[dict]) -> list[dict]:
    """Add 'email' and 'email_details' fields to each lead dict."""
    for lead in leads:
        company_name = lead.get("name", "Unknown Company")
        domain = extract_domain(lead.get("website", ""))
        
        result = get_email(lead, domain, lead.get("website", ""))
        if result:
            lead["email"] = result["email"]
            lead["email_source"] = result["source"]
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
        
        mock_lead = {"name": company_name, "website": website}
        res = get_email(mock_lead, domain, website)
        print(f"   → Result: {res}")
