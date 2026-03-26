import os
import time
import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LeadHunterBot/1.0)"}
SCRAPE_TIMEOUT = 8
MAX_TEXT_CHARS = 1500

ANALYST_SYSTEM_PROMPT = """You are a business analyst. Given homepage content from a company website,
extract key information to help write a personalized cold email.
Return ONLY a JSON object with these keys:
- industry: what type of business this is (1 short phrase)
- main_service: what they primarily sell or offer (1 sentence)
- likely_pain: what operational problem they probably face that AI automation could solve (1 sentence)
- tone: their brand tone — formal, casual, technical, creative (one word)
- hook: one specific detail from their website that could be used as a SMYKM personalization angle (1 sentence)"""


def _fallback(business: dict) -> dict:
    return {
        "industry": business.get("subreddit", "local business"),
        "main_service": "unknown",
        "likely_pain": "manual processes taking up too much time",
        "tone": "professional",
        "hook": f"a business based in {business.get('address', 'your area')}",
    }


def _scrape_homepage(url: str) -> str:
    """Fetch and extract meaningful text from a homepage. Returns up to MAX_TEXT_CHARS chars."""
    if not url.startswith("http"):
        url = f"https://{url}"

    resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    chunks = []

    # Title
    if soup.title and soup.title.string:
        chunks.append(soup.title.string.strip())

    # Meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        chunks.append(meta["content"].strip())

    # H1, H2 headings
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(strip=True)
        if text:
            chunks.append(text)

    # First several paragraphs
    for tag in soup.find_all("p"):
        text = tag.get_text(strip=True)
        if len(text) > 30:  # skip tiny/empty paragraphs
            chunks.append(text)

    combined = " | ".join(chunks)
    return combined[:MAX_TEXT_CHARS]


def _analyze_with_gpt(text: str, business_name: str) -> dict:
    """Send extracted homepage text to GPT for structured analysis."""
    user_msg = f"Business: {business_name}\n\nHomepage content:\n{text}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=300,
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    # Strip potential markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def research_company(business: dict) -> dict:
    """
    Scrape a business homepage and return a research dict for SMYKM email personalization.
    Always returns a dict — falls back gracefully on any error.

    Keys returned:
      industry, main_service, likely_pain, tone, hook
    """
    website = business.get("website", "").strip()

    if not website:
        print(f"[Research] No website for '{business.get('name')}' — using fallback.")
        return _fallback(business)

    try:
        print(f"[Research] Scraping: {website}")
        text = _scrape_homepage(website)

        if not text:
            print(f"[Research] No text extracted from {website} — using fallback.")
            return _fallback(business)

        result = _analyze_with_gpt(text, business.get("name", ""))
        time.sleep(1)  # rate limit buffer
        return result

    except requests.exceptions.RequestException as e:
        print(f"[Research] Scrape failed for {website}: {e} — using fallback.")
        return _fallback(business)
    except json.JSONDecodeError as e:
        print(f"[Research] GPT returned invalid JSON for '{business.get('name')}': {e} — using fallback.")
        return _fallback(business)
    except Exception as e:
        print(f"[Research] Unexpected error for '{business.get('name')}': {e} — using fallback.")
        return _fallback(business)
